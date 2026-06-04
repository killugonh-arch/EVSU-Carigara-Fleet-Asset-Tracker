from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import User

class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))

class UserCreateForm(forms.ModelForm):
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role', 'department', 'phone', 'license_number']
        widgets = {f: forms.TextInput(attrs={'class': 'form-control'}) for f in
                   ['username', 'first_name', 'last_name', 'email', 'phone', 'license_number']}
        widgets['department'] = forms.Select(attrs={'class': 'form-select'})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].widget.attrs['class'] = 'form-select'

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Passwords do not match.')
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Create a password'})
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm your password'})
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'department', 'phone', 'license_number']
        widgets = {
            'username':       forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Choose a username'}),
            'first_name':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name':      forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'email':          forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'}),
            'department':     forms.Select(attrs={'class': 'form-select'}),
            'phone':          forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact number'}),
            'license_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Driver's license # (if applicable)"}),
        }

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Passwords do not match.')
        return p2

    def clean_password1(self):
        p1 = self.cleaned_data.get('password1')
        if p1 and len(p1) < 8:
            raise forms.ValidationError('Password must be at least 8 characters.')
        return p1

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.role = User.STAFF          # self-registered users are always Staff
        user.is_active = True
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone',
                  'license_number', 'department', 'profile_picture']
        widgets = {
            'first_name':     forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':      forms.TextInput(attrs={'class': 'form-control'}),
            'email':          forms.EmailInput(attrs={'class': 'form-control'}),
            'phone':          forms.TextInput(attrs={'class': 'form-control'}),
            'license_number': forms.TextInput(attrs={'class': 'form-control'}),
            'department':     forms.Select(attrs={'class': 'form-select'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }
        labels = {
            'license_number': "Driver's License #",
        }