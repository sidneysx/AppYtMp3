"""
Alternativa de DNS sobre HTTPS (DoH).

Algumas redes bloqueiam a resolução de www.youtube.com pelo DNS comum, o que
faz o yt-dlp falhar com "[Errno 11001] getaddrinfo failed". Quando o DNS do
sistema falha, o nome é resolvido pelo DoH da Cloudflare e fica em cache.
"""
import json
import socket
import time
import urllib.request

DOH_URL = 'https://1.1.1.1/dns-query?name={}&type=A'

_system_getaddrinfo = socket.getaddrinfo
_cache = {}  # host -> (lista de IPs, expira_em)


def _resolve_with_doh(host):
    cached = _cache.get(host)
    if cached and cached[1] > time.monotonic():
        return cached[0]

    try:
        request = urllib.request.Request(
            DOH_URL.format(host),
            headers={'accept': 'application/dns-json'}
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            # type 1 = registro A (IPv4)
            records = [a for a in json.load(response).get('Answer', []) if a['type'] == 1]
    except Exception as e:
        raise socket.gaierror(socket.EAI_NONAME, f"DNS sobre HTTPS falhou para {host}: {e}")

    if not records:
        raise socket.gaierror(socket.EAI_NONAME, f"DNS sobre HTTPS não encontrou {host}")

    if host not in _cache:
        print(f"DNS bloqueado para {host}, usando DNS sobre HTTPS")
    ips = [r['data'] for r in records]
    _cache[host] = (ips, time.monotonic() + max(min(r['TTL'] for r in records), 60))
    return ips


def _getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    # Host que já falhou antes vai direto pro DoH, sem esperar o timeout de novo
    if host not in _cache:
        try:
            return _system_getaddrinfo(host, port, family, type, proto, flags)
        except socket.gaierror:
            if not isinstance(host, str):
                raise

    return [
        result
        for ip in _resolve_with_doh(host)
        for result in _system_getaddrinfo(ip, port, family, type, proto, flags)
    ]


def enable():
    socket.getaddrinfo = _getaddrinfo
