"""Diagnóstico do envio de e-mail do Exalte.

Uso (no terminal, com as mesmas variáveis EMAIL_* definidas):
    python testar_email.py                  -> só testa a conexão e o login
    python testar_email.py voce@email.com   -> testa e envia um e-mail de verdade
"""
import os
import smtplib
import ssl
import sys

host = (os.environ.get("EMAIL_HOST") or "smtp.gmail.com").strip()
usuario = (os.environ.get("EMAIL_USER") or "").strip()
senha = "".join((os.environ.get("EMAIL_PASSWORD") or "").split())
remetente = os.environ.get("EMAIL_FROM") or usuario
destino = sys.argv[1] if len(sys.argv) > 1 else None

print(f"Servidor: {host}")
print(f"Usuário : {usuario or '(VAZIO: defina EMAIL_USER)'}")
print(f"Senha   : {len(senha)} caracteres (senha de app do Gmail tem 16)"
      + ("" if senha.isascii() and senha.isalnum() else "  <-- tem caractere diferente de letra/número!"))
if not usuario or not senha:
    sys.exit("\nDefina EMAIL_USER e EMAIL_PASSWORD antes de rodar.")

ctx = ssl.create_default_context()


def abrir_starttls():
    s = smtplib.SMTP(host, 587, timeout=20)
    s.ehlo()
    print("   conectou na porta 587")
    s.starttls(context=ctx)
    s.ehlo()
    print("   criptografia (TLS) ok; logins aceitos:", s.esmtp_features.get("auth", "?"))
    return s


def abrir_ssl():
    s = smtplib.SMTP_SSL(host, 465, timeout=20, context=ctx)
    print("   conectou na porta 465 com SSL")
    return s


funcionou = None
for nome, abrir in (("Porta 587 (STARTTLS)", abrir_starttls), ("Porta 465 (SSL)", abrir_ssl)):
    print(f"\n== {nome}")
    try:
        s = abrir()
        s.login(usuario, senha)
        print("   LOGIN OK")
        funcionou = (nome, s)
        break
    except Exception as e:
        print(f"   FALHOU: {type(e).__name__}: {e}")

print()
if not funcionou:
    print("Nenhuma das duas portas permitiu o login.")
    print("Se as DUAS terminaram em 'Connection unexpectedly closed': desligue a verificação de e-mail/SSL do antivírus,")
    print("teste em outra rede (ex.: internet do celular) e confira se o Google mandou um alerta de segurança para a conta.")
    sys.exit(1)

nome, s = funcionou
print(f"Funcionou pela {nome}.")
if "465" in nome:
    print("Para o app usar essa porta, defina:  $env:EMAIL_SSL=\"1\"  e  $env:EMAIL_PORT=\"465\"")
if destino:
    s.sendmail(usuario, [destino], f"From: {remetente}\nTo: {destino}\nSubject: Teste do Exalte\nContent-Type: text/plain; charset=utf-8\n\nSe você leu isto, o envio de e-mail está funcionando.".encode("utf-8"))
    print(f"E-mail de teste enviado para {destino}. Confira a caixa de entrada e o spam.")
s.quit()
