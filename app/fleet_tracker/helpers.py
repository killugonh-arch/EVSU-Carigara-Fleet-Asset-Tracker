from django.http import JsonResponse


def axes_lockout_response(request, credentials, *args, **kwargs):
    return JsonResponse(
        {
            'detail': 'Account locked due to too many failed login attempts. '
                      'Try again in 15 minutes.'
        },
        status=403
    )
