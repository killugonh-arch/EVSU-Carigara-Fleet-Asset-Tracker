from django.http import JsonResponse
from django.shortcuts import redirect
from django.contrib import messages


def axes_lockout_response(request, credentials, *args, **kwargs):
    if request.headers.get("Accept", "").startswith("application/json") or \
       request.headers.get("Content-Type", "") == "application/json":
        return JsonResponse(
            {'detail': 'Account locked due to too many failed login attempts. Try again later.'},
            status=403,
        )

    messages.error(
        request,
        'This account has been locked after too many failed login attempts. '
        'Please try again in a few minutes.',
    )
    return redirect('login')
