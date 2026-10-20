from functools import wraps

from django.contrib.auth.decorators import login_required as _login_required
from django.shortcuts import redirect

from .models import Perfil


def login_required(view):
    """Exige login e, se marcado, leva a pessoa direto para a troca de senha."""
    @wraps(view)
    def wrapper(request, *a, **k):
        if Perfil.objects.filter(user=request.user, trocar_senha=True).exists():
            return redirect("alterar_senha")
        return view(request, *a, **k)
    return _login_required(wrapper)
