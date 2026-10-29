"""Notificações por e-mail e push (PWA). Envia em segundo plano para não travar a página."""
import base64
import json
import logging
import os
import threading
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.db import connection

log = logging.getLogger(__name__)


def _site():
    return os.environ.get("SITE_URL", "http://127.0.0.1:8000").rstrip("/")


def _remetente():
    return os.environ.get("EMAIL_FROM") or os.environ.get("EMAIL_USER") or "bandas@localhost"


def _conexao_email():
    host = os.environ.get("EMAIL_HOST")
    if not host:  # sem configuração: imprime o e-mail no terminal (modo de teste)
        return get_connection("django.core.mail.backends.console.EmailBackend")
    return get_connection("django.core.mail.backends.smtp.EmailBackend", host=host,
                          port=int(os.environ.get("EMAIL_PORT", "587")),
                          username=os.environ.get("EMAIL_USER"), password=os.environ.get("EMAIL_PASSWORD"),
                          use_tls=os.environ.get("EMAIL_TLS", "1") == "1", timeout=15)


def vapid_keys():
    """Chaves VAPID: variáveis de ambiente ou arquivo vapid.json (criado na primeira vez)."""
    pub, priv = os.environ.get("VAPID_PUBLIC_KEY"), os.environ.get("VAPID_PRIVATE_KEY")
    if pub and priv:
        return pub, priv
    arq = Path(settings.BASE_DIR) / "vapid.json"
    if arq.exists():
        d = json.loads(arq.read_text())
        return d["public"], d["private"]
    from cryptography.hazmat.primitives import serialization as s
    from cryptography.hazmat.primitives.asymmetric import ec
    k = ec.generate_private_key(ec.SECP256R1())
    b64 = lambda x: base64.urlsafe_b64encode(x).rstrip(b"=").decode()
    priv = b64(k.private_numbers().private_value.to_bytes(32, "big"))
    pub = b64(k.public_key().public_bytes(s.Encoding.X962, s.PublicFormat.UncompressedPoint))
    arq.write_text(json.dumps({"public": pub, "private": priv}))
    return pub, priv


def notificar(users, titulo, texto, caminho="/", exceto=None, email=True):
    """Avisa os usuários (respeitando as preferências de cada um) por e-mail e push."""
    envios, vistos = [], set()
    for u in users:
        if u.pk in vistos or (exceto and u.pk == exceto.pk):
            continue
        vistos.add(u.pk)
        p = getattr(u, "perfil", None)
        endereco = u.email if email and (p.notif_email if p else True) and u.email else None
        subs = list(u.push_subs.values_list("endpoint", "p256dh", "auth")) if (p.notif_push if p else True) else []
        if endereco or subs:
            envios.append((u.first_name or u.username, endereco, subs))
    if envios:
        threading.Thread(target=_enviar, args=(envios, titulo, texto, _site() + caminho), daemon=True).start()


def _enviar(envios, titulo, texto, url):
    try:
        msgs = [EmailMessage(f"[Exalte] {titulo}", f"Olá, {nome}!\n\n{texto}\n\nAbrir: {url}\n", _remetente(), [email])
                for nome, email, _ in envios if email]
        if msgs:
            try:
                conn = _conexao_email()
                conn.send_messages(msgs)
            except Exception:
                log.exception("Falha ao enviar e-mails")
        try:
            from pywebpush import WebPushException, webpush
            _, priv = vapid_keys()
        except Exception:
            log.warning("Push indisponível (instale pywebpush: pip install -r requirements.txt)")
            return
        mortos = []
        corpo = json.dumps({"titulo": titulo, "texto": texto, "url": url})
        sub_email = "mailto:" + (os.environ.get("VAPID_EMAIL") or os.environ.get("EMAIL_USER") or "admin@localhost.com")
        for _, _, subs in envios:
            for ep, k, a in subs:
                try:
                    webpush(subscription_info={"endpoint": ep, "keys": {"p256dh": k, "auth": a}}, data=corpo,
                            vapid_private_key=priv, vapid_claims={"sub": sub_email}, ttl=86400)
                except WebPushException as e:
                    if e.response is not None and e.response.status_code in (404, 410):
                        mortos.append(ep)
                    else:
                        log.warning("Falha no push: %s", e)
                except Exception:
                    log.exception("Falha no push")
        if mortos:
            from .models import PushSub
            PushSub.objects.filter(endpoint__in=mortos).delete()
    finally:
        connection.close()
