from django import forms
from .models import Session, ProjectSeparation, Swipe, Holiday
from django.contrib.admin.widgets import AdminDateWidget
from datetimewidget.widgets import DateTimeWidget
from datetime import timedelta, datetime
from .utils import get_number_of_work_days_in_daterange, is_workday

class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ["duration"]


class ProjectSeparationForm(forms.ModelForm):
    class Meta:
        model = ProjectSeparation
        fields = ['project', 'time_spend', 'description', 'session']
        widgets = {
                'description': forms.Textarea(attrs={
                        'cols': 50,
                        'rows': 1
                }),
                'session': forms.HiddenInput(),
        }

    def clean_time_spend(self):
        data = self.cleaned_data["time_spend"]
        if data <= timedelta(0):
            raise forms.ValidationError("Can't be zero or negative")
        return data

    def clean(self):
        cleaned_data = super(ProjectSeparationForm, self).clean()
        time_spend = cleaned_data.get("time_spend")
        session = cleaned_data.get("session")
        if time_spend and session:
            if(time_spend > cleaned_data.get("session").get_not_assigned_duration()):
                msg = "Time spend more then not assigned time"
                self.add_error('time_spend', msg)


class SwipeEditForm(forms.ModelForm):
    class Meta:
        model = Swipe
        fields = ["datetime"]

    def clean_datetime(self):
        data = self.cleaned_data["datetime"] #data passed to form
        this_swipe = self.instance
        last_swipe = this_swipe.get_last_swipe_same_user()
        next_swipe = this_swipe.get_next_swipe_same_user()

        if last_swipe:
            if data < last_swipe.datetime:
                raise forms.ValidationError("Conflict with last swipe" + str(last_swipe))
        if next_swipe:
            if data > next_swipe.datetime:
                raise forms.ValidationError("Conflict with next swipe " + str(next_swipe))

        return  data

class HolidayRequestForm(forms.ModelForm):
    class Meta:
        model = Holiday
        fields = ['date_since','date_to','work_hours','reason']
        
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(HolidayRequestForm, self).__init__(*args, **kwargs)
    
        
    def clean(self):
        date_since = self.cleaned_data["date_since"]
        date_to = self.cleaned_data["date_to"]
        quota = self.user.profile.get_hours_quota()
        hours_on_holidays = 0
        i = 0
        date = date_since
        while date <= date_to:
            if is_workday(date):
                hours_on_holidays += quota
            date += timedelta(days = 1)
        hours_on_holidays -= self.cleaned_data["work_hours"]
        min_length = quota/2
        max_length = round(self.user.profile.get_hours_of_holidays_aviable_to_take())
        if (date_since.year != datetime.now().year) or (date_to.year != datetime.now().year):
            raise forms.ValidationError("You can manage holidays for this year only.")
        if hours_on_holidays < min_length:
            raise forms.ValidationError("Length of your holiday can't be smaller than " + str(int(min_length)) + " hours")
        if get_number_of_work_days_in_daterange(date_since, date_to) * quota - hours_on_holidays > quota:
            raise forms.ValidationError("Wanna broke my work? Dont play with js!")
        if max_length < hours_on_holidays:
            raise forms.ValidationError("You can take only " + str(max_length / quota) + " days of holidays.")
        for holiday in self.user.profile.holidays.all():
            if holiday.date_since <= date_to and holiday.date_to >= date_since:
                raise forms.ValidationError("Confilct with Holiday: " + str(holiday.date_since) + "-" + str(holiday.date_to))
        
class HolidayVerifyForm(forms.ModelForm):
    class Meta:
        model = Holiday
        fields = ['verified']
