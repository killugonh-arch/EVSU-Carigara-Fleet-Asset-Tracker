"""
Member 2 (IAM): JWT login, role seeding
Member 5 (DevSecOps): audit logging on every auth event, axes lockout awareness
"""
import logging
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import LoginForm, UserCreateForm, RegisterForm
from .models import User

audit = logging.getLogger('fleet.audit')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            audit.info(f'LOGIN_SUCCESS username={user.username} ip={_ip(request)}')
            return redirect(request.GET.get('next', 'dashboard'))
        else:
            audit.warning(f'LOGIN_FAILURE username={request.POST.get("username","")} ip={_ip(request)}')
    return render(request, 'accounts/login.html', {'form': form})

def logout_view(request):
    audit.info(f'LOGOUT username={request.user.username} ip={_ip(request)}')
    logout(request)
    return redirect('login')

def register_view(request):
    """Public self-registration. Creates a Staff/Driver account pending use."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.save()
            audit.info(f'REGISTER username={user.username} ip={_ip(request)}')
            messages.success(request, f'Account created! You can now log in, {user.first_name or user.username}.')
            return redirect('login')
    return render(request, 'accounts/register.html', {'form': form})

@login_required
def user_management(request):
    if not request.user.is_manager:
        messages.error(request, 'Only managers can manage users.')
        return redirect('dashboard')
    users = User.objects.all().order_by('role', 'last_name')
    form = UserCreateForm()
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            new_user = form.save()
            audit.info(f'USER_CREATED by={request.user.username} new_user={new_user.username} role={new_user.role}')
            messages.success(request, f'User "{new_user.get_full_name() or new_user.username}" created.')
            return redirect('user_management')
    return render(request, 'accounts/user_management.html', {'users': users, 'form': form})

@login_required
def delete_user(request, pk):
    if not request.user.is_manager:
        messages.error(request, 'Only managers can delete users.')
        return redirect('user_management')
    target = get_object_or_404(User, pk=pk)
    if target == request.user:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('user_management')
    if request.method == 'POST':
        username = target.username
        target.delete()
        audit.info(f'USER_DELETED by={request.user.username} deleted_user={username}')
        messages.success(request, f'User "{username}" has been deleted.')
    return redirect('user_management')


def _ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    return x_forwarded.split(',')[0] if x_forwarded else request.META.get('REMOTE_ADDR', '?')