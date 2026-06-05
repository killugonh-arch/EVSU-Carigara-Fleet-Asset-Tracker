from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

def root_redirect(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')

urlpatterns = [
    path('', root_redirect),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', include('assets.urls')),
    path('api/', include('assets.api_urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
