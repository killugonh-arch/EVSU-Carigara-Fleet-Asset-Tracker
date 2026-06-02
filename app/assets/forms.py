from django import forms
from .models import Asset, MaintenanceRequest, MileageLog, MaintenanceFrequency

W = {'class': 'form-control'}
S = {'class': 'form-select'}

class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = [
            # Basic Info — asset_tag, location, serial_number, make removed
            'asset_type', 'name', 'model_name', 'year',
            'status', 'department',
            # Financial
            'procurement_cost', 'current_value', 'procurement_date',
            # Vehicle Details
            'mileage', 'fuel_type', 'license_plate', 'next_service_km',
            # Maintenance Schedule — only first date + frequency
            'first_maintenance_date', 'maintenance_frequency',
            'notes',
        ]
        widgets = {
            'asset_type': forms.Select(attrs=S),
            'status':     forms.Select(attrs=S),
            'maintenance_frequency': forms.Select(attrs=S),
            'notes':      forms.Textarea(attrs={**W, 'rows': 3}),
            'first_maintenance_date': forms.DateInput(attrs={**W, 'type': 'date'}),
            'procurement_date':       forms.DateInput(attrs={**W, 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not field.widget.attrs.get('class'):
                field.widget.attrs['class'] = 'form-control'

class MaintenanceRequestForm(forms.ModelForm):
    class Meta:
        model  = MaintenanceRequest
        fields = ['asset', 'title', 'description', 'priority', 'estimated_cost', 'requested_date', 'vendor', 'notes']
        widgets = {
            'asset':          forms.Select(attrs=S),
            'title':          forms.HiddenInput(),
            'priority':       forms.Select(attrs=S),
            'description':    forms.Textarea(attrs={**W, 'rows': 4}),
            'notes':          forms.Textarea(attrs={**W, 'rows': 3}),
            'requested_date': forms.DateInput(attrs={**W, 'type': 'date'}),
            'estimated_cost': forms.NumberInput(attrs=W),
            'vendor':         forms.TextInput(attrs=W),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].required = False

class MaintenanceApprovalForm(forms.ModelForm):
    class Meta:
        model  = MaintenanceRequest
        fields = ['scheduled_date', 'vendor', 'actual_cost', 'notes']
        widgets = {
            'scheduled_date': forms.DateInput(attrs={**W, 'type': 'date'}),
            'vendor':         forms.TextInput(attrs=W),
            'actual_cost':    forms.NumberInput(attrs=W),
            'notes':          forms.Textarea(attrs={**W, 'rows': 3}),
        }

class MileageLogForm(forms.ModelForm):
    class Meta:
        model  = MileageLog
        fields = ['asset', 'odometer', 'trip_km', 'log_date', 'purpose', 'notes']
        widgets = {
            'asset':    forms.Select(attrs=S),
            'log_date': forms.DateInput(attrs={**W, 'type': 'date'}),
            'purpose':  forms.TextInput(attrs=W),
            'notes':    forms.Textarea(attrs={**W, 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['asset'].queryset = Asset.objects.filter(asset_type='vehicle')
        for f in ['odometer', 'trip_km']:
            self.fields[f].widget.attrs['class'] = 'form-control'


class AssetRequestForm(forms.ModelForm):
    """Staff form to request procurement of a new asset."""
    W = {'class': 'form-control'}
    S = {'class': 'form-select'}

    class Meta:
        from .models import AssetRequest
        model  = AssetRequest
        fields = ['asset_type', 'name', 'make', 'model_name', 'justification', 'estimated_cost']
        widgets = {
            'asset_type':     forms.Select(attrs={'class': 'form-select'}),
            'name':           forms.TextInput(attrs={'class': 'form-control'}),
            'make':           forms.TextInput(attrs={'class': 'form-control'}),
            'model_name':     forms.TextInput(attrs={'class': 'form-control'}),
            'justification':  forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'estimated_cost': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class AssetRequestReviewForm(forms.ModelForm):
    """Manager form to approve/reject an asset request."""
    class Meta:
        from .models import AssetRequest
        model  = AssetRequest
        fields = ['manager_notes']
        widgets = {
            'manager_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }