from django.shortcuts import redirect
from django.urls import reverse_lazy

class AnonymousRequiredMixin:
    """
    Redirect authenticated users away from views meant for anonymous users
    (like login or register).
    """

    redirect_url = reverse_lazy("core:home")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.redirect_url)
        return super().dispatch(request, *args, **kwargs)
