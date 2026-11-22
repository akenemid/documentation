"""Réseau commun du moteur : une seule session HTTP, liste blanche des hôtes, plafonds et délais.

Tout le code qui va sur le réseau (téléchargement des BOC, cours du jour, recherche des notes : pages,
listes, documents, page fournie par l'analyste) passe par :func:`creer_session` (la session
``requests`` unique du processus : :func:`session_partagee`) et :class:`ClientHttp`. Les règles de
politesse (10 s entre deux requêtes vers brvm.org, arrêt au premier 403 ou 429, ``Crawl-delay``)
restent celles de ``brvm_alpha.notes.research.PoliteSession`` et de
``brvm_alpha.data.boc_download.PoliteFetcher`` ; ce module ajoute les contrôles de sûreté :

- **liste blanche** des hôtes (:class:`Politique`) : ``www.brvm.org`` et ``brvm.org`` par défaut ; une
  source facultative (Sika Finance, Richbourse, presse : :data:`SOURCES_FACULTATIVES`), désactivée par
  défaut, n'ajoute son domaine que si elle est explicitement activée. Schéma ``https`` seulement, port
  par défaut, aucun identifiant dans l'adresse ;
- contrôle de la liste blanche sur la requête **et** sur chaque redirection (redirections gérées à la
  main, :data:`MAX_REDIRECTIONS` au plus), refus d'une redirection ``https`` → ``http`` ;
- refus des adresses de boucle locale, privées, de lien local, réservées ou de multidiffusion **après
  résolution DNS** (sauf passage par un mandataire, qui résout lui-même) ;
- **plafond de taille** lu en flux, par nature de réponse (:data:`PLAFONDS` : page, robots.txt, PDF),
  décompression comprise (gzip, deflate) : lecture arrêtée au-delà du plafond ;
- **délai total** par requête (connexion + lecture, :data:`DELAIS_TOTAUX`), en plus du délai par
  opération ;
- mode embarqué (:func:`brvm_alpha.paths.est_embarque`) : la session ne fait **pas** confiance à
  l'environnement (``trust_env=False`` : ni ``HTTPS_PROXY``, ni ``.netrc``, ni ``REQUESTS_CA_BUNDLE``) ;
  un mandataire n'est utilisé que s'il est donné par ``BRVM_ALPHA_PROXY``. Hors mode embarqué, le
  comportement de ``requests`` est conservé (mandataire de l'environnement).

Toute violation lève :class:`~brvm_alpha.erreurs.AccesRefuse` (code de sortie 5) : une sous-classe de
:class:`RefusPolitique` (définitive : aucun nouvel essai) ou de :class:`ErreurReseau` (passagère :
délai dépassé, connexion impossible). ``MemoryError`` n'est jamais traitée comme une erreur réseau.
"""

from __future__ import annotations

import ipaddress
import os
import socket
import threading
import time
import zlib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any
from urllib.parse import urljoin, urlsplit

from brvm_alpha import paths
from brvm_alpha.erreurs import AccesRefuse

USER_AGENT = "brvm-alpha/0.1 (outil d'analyse personnel)"
#: Variable d'environnement du mandataire explicite (seul mandataire utilisé en mode embarqué).
ENV_PROXY = "BRVM_ALPHA_PROXY"
#: Hôtes toujours permis.
HOTES_BRVM = frozenset({"www.brvm.org", "brvm.org"})
#: Sources facultatives (désactivées par défaut) : domaines ajoutés seulement si la source est activée.
SOURCES_FACULTATIVES: Mapping[str, tuple[str, ...]] = MappingProxyType({
    "sikafinance": ("sikafinance.com",),
    "richbourse": ("richbourse.com",),
    "presse": ("financialafrik.com", "agenceecofin.com", "abidjan.net"),
})
#: Plafond de taille par nature de réponse (octets, après décompression).
PLAFONDS: Mapping[str, int] = MappingProxyType({"page": 8 * 2 ** 20, "robots": 512 * 2 ** 10, "pdf": 64 * 2 ** 20})
#: Délai total par requête (s) : connexion, en-têtes et corps compris.
DELAIS_TOTAUX: Mapping[str, float] = MappingProxyType({"page": 90.0, "robots": 30.0, "pdf": 300.0})
#: Délais par opération (s) : connexion, et attente entre deux octets reçus.
DELAI_CONNEXION_S = 15.0
DELAI_LECTURE_S = 60.0
MAX_REDIRECTIONS = 5
STATUTS_REDIRECTION = frozenset({301, 302, 303, 307, 308})
_PORTS_DEFAUT = {"http": 80, "https": 443}
_BLOC = 64 * 1024


# ---------------------------------------------------------------------------
# Erreurs (toutes : code de sortie 5)
# ---------------------------------------------------------------------------


class ErreurReseau(AccesRefuse):
    """Erreur passagère du réseau (délai dépassé, connexion impossible) : un nouvel essai est permis."""


class DelaiDepasse(ErreurReseau):
    """Délai par opération ou délai total de la requête dépassé."""


class ConnexionImpossible(ErreurReseau):
    """Connexion impossible ou coupée (nom introuvable, refus, coupure en cours de lecture)."""


class RefusPolitique(AccesRefuse):
    """Refus définitif de la politique de sûreté : aucun nouvel essai."""


class HoteNonAutorise(RefusPolitique):
    """Hôte, schéma, port ou forme d'adresse hors de la liste blanche."""


class RedirectionRefusee(RefusPolitique):
    """Redirection refusée (``https`` → ``http``, ou vers un hôte hors liste)."""


class TropDeRedirections(RefusPolitique):
    """Plus de :data:`MAX_REDIRECTIONS` redirections."""


class AdresseInterdite(RefusPolitique):
    """Le nom se résout en adresse de boucle locale, privée, de lien local ou réservée."""


class ReponseTropGrosse(RefusPolitique):
    """Réponse au-delà du plafond de taille de sa nature (page, robots.txt, PDF)."""


class EncodageRefuse(RefusPolitique):
    """Encodage de transfert inconnu (seuls gzip et deflate sont décompressés)."""


# ---------------------------------------------------------------------------
# Politique : liste blanche, plafonds, délais
# ---------------------------------------------------------------------------


def _hote_port(url: str) -> tuple[str, str, int | None, bool]:
    """``(schéma, hôte normalisé, port, identifiants présents)`` ; ``ValueError`` si l'adresse est illisible."""
    p = urlsplit(str(url or ""))
    host = (p.hostname or "").lower().rstrip(".")
    port = p.port  # ValueError pour un port illisible
    return (p.scheme or "").lower(), host, port, bool(p.username or p.password)


@dataclass(frozen=True)
class Politique:
    """Règles de sûreté d'un client : hôtes permis, schémas, plafonds, délais.

    ``hotes`` : hôtes exacts (« www.brvm.org », ou « hôte:port » pour un port autre que celui du
    schéma) ; ``domaines`` : domaines permis avec leurs sous-domaines (sources facultatives activées) ;
    ``adresses_locales`` : accepte la boucle locale et les adresses privées (essais seulement).
    """

    hotes: frozenset[str] = HOTES_BRVM
    domaines: frozenset[str] = frozenset()
    schemas: frozenset[str] = frozenset({"https"})
    adresses_locales: bool = False
    plafonds: Mapping[str, int] = field(default_factory=lambda: dict(PLAFONDS))
    delais: Mapping[str, float] = field(default_factory=lambda: dict(DELAIS_TOTAUX))
    delai_connexion: float = DELAI_CONNEXION_S
    delai_lecture: float = DELAI_LECTURE_S
    max_redirections: int = MAX_REDIRECTIONS

    def plafond(self, nature: str) -> int:
        return int(self.plafonds.get(nature, self.plafonds.get("page", PLAFONDS["page"])))

    def delai_total(self, nature: str) -> float:
        return float(self.delais.get(nature, self.delais.get("page", DELAIS_TOTAUX["page"])))

    def avec_hotes(self, *hotes: str) -> Politique:
        """Copie avec des hôtes exacts en plus."""
        return replace(self, hotes=frozenset(self.hotes) | {str(h).lower().rstrip(".") for h in hotes if h})

    def refus(self, url: str) -> str | None:
        """Motif du refus de ``url`` (texte français), ou ``None`` si elle est permise."""
        try:
            scheme, host, port, creds = _hote_port(url)
        except ValueError:
            return f"adresse illisible : {str(url)[:200]!r}"
        if scheme not in self.schemas:
            return f"schéma « {scheme or '?'} » refusé ({' ou '.join(sorted(self.schemas))} attendu) : {url}"
        if not host:
            return f"adresse sans hôte : {url}"
        if creds:
            return f"identifiants dans l'adresse refusés : {scheme}://…@{host}"
        default = port is None or port == _PORTS_DEFAUT.get(scheme)
        if f"{host}:{port}" in self.hotes:
            return None
        if default and (host in self.hotes or any(host == d or host.endswith("." + d) for d in self.domaines)):
            return None
        where = host if default else f"{host}:{port}"
        return (f"hôte {where} hors de la liste blanche ({', '.join(sorted(self.hotes | self.domaines))}) : "
                "aucune requête n'y est envoyée")

    def controler(self, url: str, depuis: str | None = None) -> None:
        """Lève :class:`HoteNonAutorise` (ou :class:`RedirectionRefusee` pour un saut) si ``url`` est refusée."""
        if depuis is not None:
            try:
                before, after = urlsplit(str(depuis)).scheme.lower(), urlsplit(str(url)).scheme.lower()
            except ValueError:
                before = after = ""
            if before == "https" and after == "http":
                raise RedirectionRefusee(f"redirection de {depuis} vers {url} refusée (https vers http).")
        why = self.refus(url)
        if why:
            cls = RedirectionRefusee if depuis is not None else HoteNonAutorise
            raise cls(f"redirection de {depuis} refusée : {why}" if depuis is not None else why)


def domaines_des_sources(sources: Iterable[str] | bool = ()) -> frozenset[str]:
    """Domaines des sources facultatives activées (``True`` : toutes)."""
    if sources is True:
        names = list(SOURCES_FACULTATIVES)
    elif not sources:
        names = []
    else:
        names = [str(s).strip().lower() for s in sources]  # type: ignore[union-attr]
    unknown = [n for n in names if n not in SOURCES_FACULTATIVES]
    if unknown:
        raise ValueError(f"source facultative inconnue : {', '.join(unknown)} ({', '.join(SOURCES_FACULTATIVES)})")
    return frozenset(d for n in names for d in SOURCES_FACULTATIVES[n])


def politique_par_defaut(sources: Iterable[str] | bool = (), hotes: Iterable[str] = ()) -> Politique:
    """Politique du moteur : brvm.org seulement, plus les sources facultatives **explicitement** activées."""
    pol = Politique(domaines=domaines_des_sources(sources))
    return pol.avec_hotes(*hotes) if hotes else pol


def adresse_interdite(ip: str) -> bool:
    """Vrai pour une adresse de boucle locale, privée, de lien local, réservée, non routée ou de multidiffusion."""
    try:
        addr = ipaddress.ip_address(str(ip).split("%", 1)[0])
    except ValueError:
        return True
    mapped = getattr(addr, "ipv4_mapped", None)
    if mapped is not None:
        addr = mapped
    return (not addr.is_global or addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast
            or addr.is_reserved or addr.is_unspecified)


# ---------------------------------------------------------------------------
# Session requests commune
# ---------------------------------------------------------------------------


def mandataire_explicite(environ: Mapping[str, str] | None = None) -> str | None:
    """Mandataire donné par ``BRVM_ALPHA_PROXY`` (``None`` s'il est vide)."""
    raw = str((os.environ if environ is None else environ).get(ENV_PROXY, "") or "").strip()
    return raw or None


def creer_session(user_agent: str = USER_AGENT, environ: Mapping[str, str] | None = None) -> Any:
    """La session ``requests`` du moteur (fonction commune à tout le code qui va sur le réseau).

    Mode embarqué : ``trust_env=False`` (l'environnement est ignoré : mandataire, ``.netrc``, autorités
    de certification) ; mandataire seulement par ``BRVM_ALPHA_PROXY``. Hors mode embarqué : comportement
    de ``requests`` conservé, ``BRVM_ALPHA_PROXY`` l'emportant s'il est posé. Aucun nouvel essai
    automatique, aucune redirection suivie par ``requests``.
    """
    import requests
    from requests.adapters import HTTPAdapter

    sess = requests.Session()
    if paths.est_embarque(environ):
        sess.trust_env = False
    proxy = mandataire_explicite(environ)
    if proxy:
        sess.proxies = {"http": proxy, "https": proxy}
    sess.headers["User-Agent"] = user_agent
    sess.max_redirects = MAX_REDIRECTIONS
    for prefix in ("https://", "http://"):
        sess.mount(prefix, HTTPAdapter(max_retries=0, pool_connections=2, pool_maxsize=4))
    return sess


_SESSION: Any = None
_SESSION_LOCK = threading.Lock()


def session_partagee() -> Any:
    """Session unique du processus (créée à la première requête par :func:`creer_session`)."""
    global _SESSION
    with _SESSION_LOCK:
        if _SESSION is None:
            _SESSION = creer_session()
        return _SESSION


def reinitialiser_session() -> None:
    """Oublie la session partagée (essais ; changement d'environnement)."""
    global _SESSION
    with _SESSION_LOCK:
        if _SESSION is not None:
            try:
                _SESSION.close()
            except Exception:  # pragma: no cover
                pass
        _SESSION = None


def via_mandataire(url: str, session: Any) -> bool:
    """Vrai si ``session`` enverra ``url`` à un mandataire (qui résout alors le nom lui-même)."""
    try:
        from requests.utils import get_environ_proxies, select_proxy
    except ImportError:  # pragma: no cover
        return False
    proxies = dict(getattr(session, "proxies", None) or {})
    if getattr(session, "trust_env", False):
        for k, v in (get_environ_proxies(url) or {}).items():
            proxies.setdefault(k, v)
    return bool(select_proxy(url, proxies))


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


@dataclass
class Reponse:
    """Réponse lue en entier (dans les plafonds) ; mêmes noms d'attributs que ``requests.Response``."""

    status_code: int
    content: bytes
    headers: dict[str, str]
    url: str

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


def _decodeur(encoding: str) -> Any:
    enc = (encoding or "").strip().lower()
    if enc in ("", "identity"):
        return None
    if enc in ("gzip", "x-gzip"):
        return zlib.decompressobj(16 + zlib.MAX_WBITS)
    if enc == "deflate":
        return zlib.decompressobj(zlib.MAX_WBITS)
    raise EncodageRefuse(f"encodage de transfert « {encoding} » non pris en charge (gzip ou deflate attendu).")


class ClientHttp:
    """Client HTTP du moteur : une requête GET à la fois, avec tous les contrôles du module.

    ``politique`` : :class:`Politique` (défaut : :func:`politique_par_defaut`) ; ``session`` : session
    ``requests`` (défaut : :func:`session_partagee`) ; ``resolveur`` et ``horloge`` : injectables
    (essais). Les règles de politesse ne sont pas ici (voir le module).
    """

    def __init__(self, politique: Politique | None = None, *, user_agent: str = USER_AGENT, session: Any = None,
                 resolveur: Callable[..., Any] | None = None, horloge: Callable[[], float] = time.monotonic) -> None:
        self.politique = politique or politique_par_defaut()
        self.user_agent = user_agent
        self._session = session
        self.resolveur = resolveur or socket.getaddrinfo
        self.horloge = horloge

    @property
    def session(self) -> Any:
        return self._session if self._session is not None else session_partagee()

    def _controler_adresses(self, url: str) -> None:
        if self.politique.adresses_locales:
            return
        _scheme, host, port, _ = _hote_port(url)
        try:
            ipaddress.ip_address(host)
            literal = True
        except ValueError:
            literal = False
        if literal:
            if adresse_interdite(host):
                raise AdresseInterdite(f"adresse {host} interdite (boucle locale, privée ou réservée) : {url}")
            return
        if via_mandataire(url, self.session):
            return  # le mandataire résout le nom : la liste blanche suffit
        try:
            infos = self.resolveur(host, port or _PORTS_DEFAUT.get(_scheme, 443), 0, socket.SOCK_STREAM)
        except (socket.gaierror, UnicodeError, OSError) as exc:
            raise ConnexionImpossible(f"nom {host} introuvable ({exc}).") from exc
        bad = sorted({str(info[4][0]) for info in infos if adresse_interdite(str(info[4][0]))})
        if bad:
            raise AdresseInterdite(f"{host} se résout en adresse interdite ({', '.join(bad)}) : aucune requête n'est "
                                   "envoyée.")

    def get(self, url: str, *, en_tetes: Mapping[str, str] | None = None, nature: str = "page", suivre: int = 0,
            delai_lecture: float | None = None) -> Reponse:
        """GET de ``url`` ; ``suivre`` : redirections suivies (chacune contrôlée), 0 = aucune (3xx rendu tel quel)."""
        cur, before = str(url), None
        for hop in range(max(0, int(suivre)) + 1):
            self.politique.controler(cur, depuis=before)
            self._controler_adresses(cur)
            res = self._requete(cur, en_tetes or {}, nature, delai_lecture)
            loc = res.headers.get("Location") or res.headers.get("location")
            if res.status_code not in STATUTS_REDIRECTION or not loc or suivre <= 0:
                return res
            if hop >= suivre:
                raise TropDeRedirections(f"{url} : plus de {suivre} redirections, page non lue.")
            before, cur = cur, urljoin(cur, loc)
        raise TropDeRedirections(f"{url} : trop de redirections.")  # pragma: no cover

    def _requete(self, url: str, en_tetes: Mapping[str, str], nature: str, delai_lecture: float | None) -> Reponse:
        import requests

        pol = self.politique
        total = pol.delai_total(nature)
        cap = pol.plafond(nature)
        start = self.horloge()
        deadline = start + total
        read_to = min(float(delai_lecture or pol.delai_lecture), total)
        headers = {"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate", **dict(en_tetes)}
        try:
            resp = self.session.get(url, headers=headers, timeout=(min(pol.delai_connexion, total), read_to),
                                    allow_redirects=False, stream=True)
        except requests.exceptions.Timeout as exc:
            raise DelaiDepasse(f"{url} : délai dépassé ({exc.__class__.__name__}).") from exc
        except requests.exceptions.RequestException as exc:
            raise ConnexionImpossible(f"{url} : {exc.__class__.__name__}: {exc}") from exc
        try:
            rheaders = {str(k): str(v) for k, v in dict(resp.headers or {}).items()}
            length = rheaders.get("Content-Length") or rheaders.get("content-length")
            if length and length.strip().isdigit() and int(length) > cap:
                raise ReponseTropGrosse(f"{url} : {int(length)} octets annoncés, plafond {cap} ({nature}).")
            body = self._lire(resp, url, cap, deadline, nature, rheaders)
            status = int(resp.status_code)
            final = str(getattr(resp, "url", None) or url)
        finally:
            try:
                resp.close()
            except Exception:  # pragma: no cover
                pass
        if self.horloge() > deadline:
            raise DelaiDepasse(f"{url} : délai total de {total:.0f} s dépassé ({nature}).")
        return Reponse(status_code=status, content=body, headers=rheaders, url=final)

    def _lire(self, resp: Any, url: str, cap: int, deadline: float, nature: str, headers: Mapping[str, str]) -> bytes:
        import requests

        raw = getattr(resp, "raw", None)
        if raw is None or not hasattr(raw, "read"):  # réponse fabriquée (essais) : contenu déjà en mémoire
            data = bytes(getattr(resp, "_content", None) or b"")
            if len(data) > cap:
                raise ReponseTropGrosse(f"{url} : réponse de plus de {cap} octets ({nature}).")
            return data
        dec = _decodeur(headers.get("Content-Encoding") or headers.get("content-encoding") or "")
        out = bytearray()
        n_raw = 0
        read1 = getattr(raw, "read1", None)
        try:
            while True:
                if self.horloge() > deadline:
                    raise DelaiDepasse(f"{url} : délai total dépassé pendant la lecture ({nature}).")
                chunk = read1(_BLOC, decode_content=False) if read1 is not None else raw.read(16 * 1024,
                                                                                            decode_content=False)
                if not chunk:
                    break
                n_raw += len(chunk)
                if n_raw > cap:
                    raise ReponseTropGrosse(f"{url} : réponse de plus de {cap} octets ({nature}) : lecture arrêtée.")
                if dec is None:
                    out += chunk
                else:
                    out += dec.decompress(chunk, cap + 1 - len(out))
                    if dec.unconsumed_tail or len(out) > cap:
                        raise ReponseTropGrosse(f"{url} : réponse décompressée de plus de {cap} octets ({nature}).")
                if len(out) > cap:
                    raise ReponseTropGrosse(f"{url} : réponse de plus de {cap} octets ({nature}) : lecture arrêtée.")
            if dec is not None:
                out += dec.flush()
                if len(out) > cap:
                    raise ReponseTropGrosse(f"{url} : réponse décompressée de plus de {cap} octets ({nature}).")
        except (MemoryError, AccesRefuse):
            raise
        except zlib.error as exc:
            raise ConnexionImpossible(f"{url} : contenu compressé illisible ({exc}).") from exc
        except Exception as exc:  # coupure, délai entre deux octets
            import urllib3

            if isinstance(exc, (TimeoutError, socket.timeout, urllib3.exceptions.TimeoutError,
                                requests.exceptions.Timeout)):
                raise DelaiDepasse(f"{url} : délai de lecture dépassé ({exc.__class__.__name__}).") from exc
            raise ConnexionImpossible(f"{url} : lecture interrompue ({exc.__class__.__name__}: {exc}).") from exc
        return bytes(out)


def transport_http(user_agent: str = USER_AGENT, politique: Politique | None = None,
                   client: ClientHttp | None = None) -> Callable[..., Reponse]:
    """Transport ``(url, en-têtes, délai, nature=…) -> Reponse`` pour ``PoliteSession`` (aucune redirection suivie)."""
    cli = client or ClientHttp(politique, user_agent=user_agent)

    def transport(url: str, headers: Mapping[str, str], timeout: float, nature: str = "page") -> Reponse:
        return cli.get(url, en_tetes=headers, nature=nature, suivre=0, delai_lecture=timeout)

    transport.accepte_nature = True  # type: ignore[attr-defined]
    transport.client = cli  # type: ignore[attr-defined]
    return transport


__all__ = ["USER_AGENT", "ENV_PROXY", "HOTES_BRVM", "SOURCES_FACULTATIVES", "PLAFONDS", "DELAIS_TOTAUX",
           "DELAI_CONNEXION_S", "DELAI_LECTURE_S", "MAX_REDIRECTIONS", "STATUTS_REDIRECTION", "ErreurReseau",
           "DelaiDepasse", "ConnexionImpossible", "RefusPolitique", "HoteNonAutorise", "RedirectionRefusee",
           "TropDeRedirections", "AdresseInterdite", "ReponseTropGrosse", "EncodageRefuse", "Politique",
           "domaines_des_sources", "politique_par_defaut", "adresse_interdite", "mandataire_explicite",
           "creer_session", "session_partagee", "reinitialiser_session", "via_mandataire", "Reponse", "ClientHttp",
           "transport_http"]
