# 🎸 Bandas - organizador de bandas (Django)

    pip install -r requirements.txt
    python manage.py makemigrations core
    python manage.py migrate
    python manage.py seed        # dados de exemplo (opcional)
    python manage.py runserver

Acesse http://127.0.0.1:8000  (admin/admin123 ou ana/senha123 com o seed).
Líderes cadastram bandas, membros, eventos, escalas, setlists e avisos em /admin/
(marque "Membro da equipe" no usuário). Músicos usam o site para ver escala,
confirmar presença, registrar indisponibilidade e consultar repertório.
