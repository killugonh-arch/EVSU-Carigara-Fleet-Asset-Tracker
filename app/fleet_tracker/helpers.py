from django.http import JsonResponse
from django.shortcuts import render
from fleet_tracker.settings import AXES_COOLOFF_TIME


def axes_lockout_response(request, credentials, *args, **kwargs):
    # API / JSON clients
    if request.headers.get("Accept", "").startswith("application/json") or \
       request.headers.get("Content-Type", "") == "application/json":
        return JsonResponse(
            {'detail': 'Account locked due to too many failed login attempts. Try again later.'},
            status=403,
        )

    # Browser: render the login page with lockout banner + disabled form
    try:
        minutes = int(AXES_COOLOFF_TIME.total_seconds() // 60)
    except Exception:
        minutes = 15

    locked_username = (credentials or {}).get('username', '') or request.POST.get('username', '')

    from accounts.forms import LoginForm
    return render(request, 'accounts/login.html', {
        'form': LoginForm(),
        'lockout': True,
        'lockout_minutes': minutes,
        'locked_username': locked_username,
    }, status=403)
