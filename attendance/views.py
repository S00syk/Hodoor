from django.shortcuts import render, get_object_or_404, render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse
from rest_framework import viewsets
from .serializers import SwipeSerializer,UserSerializer,KeySerializer
from .models import Swipe, Key, Session,ProjectSeparation, Project
from django.contrib.auth.models import User
from django.views.generic import ListView, DetailView
from django.contrib.auth.decorators import login_required
from rest_framework import permissions
from datetime import datetime, date, timedelta
from .forms import ProjectSeparationForm, SwipeEditForm
from django.utils import timezone
from django.db.models import Q
from calendar import monthrange
import locale
from django.db.models import Prefetch
import csv
from .xlsx_generator import make_administration_report
from attendance.utils import get_quota_work_hours, get_num_of_elapsed_workdays_in_month, get_number_of_work_days, last_month, daily_hours, timedelta_to_hours
from czech_holidays import holidays as czech_holidays
from django.template.loader import render_to_string
from weasyprint import HTML
import tempfile

WORKHOURS_PER_DAY = 8

@login_required(login_url='/login/')
def home_page(request):
    return HttpResponseRedirect(reverse(user, args=[request.user.username]))
class SwipeViewSet(viewsets.ModelViewSet):
    '''
    API end point for posting swipes
    '''
    queryset = Swipe.objects.all().order_by("-datetime")[:20]
    serializer_class = SwipeSerializer
    http_method_names = ['post','get']
    permission_classes = (permissions.IsAuthenticated,)

class KeyViewSet(viewsets.ModelViewSet):
    queryset = Key.objects.all()
    serializer_class = KeySerializer
    http_method_names = ['get',]
    permission_classes = (permissions.IsAuthenticated,)

def user_check(request, username):
    #superuser should be able to see all profiles
    if request.user.get_username() == username or request.user.is_superuser or request.user.is_staff:
        return True
    else:
        return False

@login_required(login_url='/login/')
def user(request, username):
    if not user_check(request, username):
        return HttpResponse("Restricted to " + username)
    if request.method == "POST":
        if request.POST.get("IN"):
            Swipe.objects.create(
                    swipe_type = "IN",
                    user = request.user,
                    datetime = timezone.now(),
            )
        if request.POST.get("OUT"):
            Swipe.objects.create(
                    swipe_type = "OUT",
                    user = request.user,
                    datetime = timezone.now(),
            )
        if request.POST.get("OBR"):
            Swipe.objects.create(
                    swipe_type = "OBR",
                    user = request.user,
                    datetime = timezone.now(),
            )
        if request.POST.get("FBR"):
            Swipe.objects.create(
                    swipe_type = "FBR",
                    user = request.user,
                    datetime = timezone.now(),
            )
        if request.POST.get("OTR"):
            Swipe.objects.create(
                    swipe_type = "OTR",
                    user = request.user,
                    datetime = timezone.now(),
            )
        if request.POST.get("FTR"):
            Swipe.objects.create(
                    swipe_type = "FTR",
                    user = request.user,
                    datetime = timezone.now(),
            )
        if request.POST.get("OUTUSER"):
            if (request.user.is_staff)or(request.user.is_superuser):
                if request.POST.get("OUTUSER")=="SwipeUserOut":
                    Swipe.objects.create(
                          swipe_type = "OUT",
                          user = User.objects.get(username=(request.POST.get("username"))),
                          datetime = timezone.now(),
                    )
                elif request.POST.get("OUTUSER")=="BreakUserOut":
                    Swipe.objects.create(
                          swipe_type = "FBR",
                          user = User.objects.get(username=(request.POST.get("username"))),
                          datetime = timezone.now(),
                    )
                    Swipe.objects.create(
                          swipe_type = "OUT",
                          user = User.objects.get(username=(request.POST.get("username"))),
                          datetime = timezone.now(),
                    )
                elif request.POST.get("OUTUSER")=="TripUserOut":
                    Swipe.objects.create(
                          swipe_type = "FTR",
                          user = User.objects.get(username=(request.POST.get("username"))),
                          datetime = timezone.now(),
                    )
                    Swipe.objects.create(
                          swipe_type = "OUT",
                          user = User.objects.get(username=(request.POST.get("username"))),
                          datetime = timezone.now(),
                    )
        return HttpResponseRedirect(reverse(user, args=[request.user.username])); # hard reload the page without any forms
    u = User.objects.get(username=username)
    s = Session.objects.get_sessions_this_month(user=u)

    open_sessions = Session.objects.get_open_sessions()
    try:
        current_session = open_sessions.filter(user=u)[0]
        current_session_work_hours = current_session.session_duration().seconds / 3600
    except:
        current_session = None
        current_session_work_hours = 0

    latest_swipes = []

    for session in open_sessions:
        latest_swipes.append(
            Swipe.objects.filter(session=session).order_by("-datetime")[0]
        )

    at_work_users, on_break_users, on_trip_users = [], [], []

    for swipe in latest_swipes:
        if swipe.swipe_type == "IN" or swipe.swipe_type == "FBR" or swipe.swipe_type == "FTR":
            at_work_users.append(swipe.user)
        elif swipe.swipe_type == "OBR":
            on_break_users.append(swipe.user)
        elif swipe.swipe_type == "OTR":
            on_trip_users.append(swipe.user)

    try:
        last_swipe = Swipe.objects.filter(user=u).order_by("-datetime")[0]
        next_swipes = last_swipe.get_next_allowed_types()
    except IndexError:
        last_swipe = None
        next_swipes = ('IN',)  # empty database - first swipe is IN

    last_month_ = last_month()
    if last_month == 12:
        year = datetime.now().year - 1
    else:
        year = datetime.now().year

    hours_total_last_month = Session.objects.get_hours_month(u.id, last_month_, year)
    hours_unassigned_last_month = Session.objects.get_unassigned_hours_month(u.id, last_month_, year)
    hours_total_this_month = Session.objects.get_hours_this_month(u.id)
    hours_unassigned_this_month = Session.objects.get_unassigned_hours_month(u.id, datetime.now().month, year)
    hours_not_work_this_month = Session.objects.get_not_work_hours_month(u.id, datetime.now().month, datetime.now().year)
    hours_not_work_last_month = Session.objects.get_not_work_hours_month(u.id, last_month_, year)
    hours_work_last_month = hours_total_last_month - hours_unassigned_last_month - hours_not_work_last_month
    hours_work_this_month = hours_total_this_month - hours_unassigned_this_month - hours_not_work_this_month

    num_of_workdays = get_number_of_work_days(date.today().year, date.today().month)
    unassigned_closed_session_hours = hours_unassigned_this_month - current_session_work_hours
    hours_quota = get_quota_work_hours(datetime.now().year, datetime.now().month, WORKHOURS_PER_DAY)
    num_of_elapsed_workdays = get_num_of_elapsed_workdays_in_month(date.today())
    num_of_elapsed_workdays_last_month = get_number_of_work_days(datetime.now().year, last_month_)
    current_quota = num_of_elapsed_workdays * WORKHOURS_PER_DAY
    hours_quota_last_month = num_of_elapsed_workdays_last_month * WORKHOURS_PER_DAY
    quota_difference = hours_work_this_month + unassigned_closed_session_hours - current_quota
    quota_difference_abs = abs(quota_difference)
    hours_quota_dif_last_month = hours_work_last_month + hours_unassigned_last_month - hours_quota_last_month
    avg_work_hours_fullfill_quota = daily_hours((hours_quota - unassigned_closed_session_hours - hours_work_this_month) / max(1,num_of_workdays - num_of_elapsed_workdays))
    
    context = {
        "user": u,
        "session_list": s,
        "hours_total_this_month": hours_total_this_month,
        "hours_unassigned_this_month": hours_unassigned_this_month,
        "last_swipe": last_swipe,
        "next_swipes": next_swipes,
        "at_work_users": at_work_users,
        "on_break_users": on_break_users,
        "on_trip_users": on_trip_users,
        "hours_total_last_month": hours_total_last_month,
        "hours_unassigned_last_month": hours_unassigned_last_month,
        "hours_not_work_this_month": hours_not_work_this_month,
        "hours_not_work_last_month": hours_not_work_last_month,
        "hours_work_last_month": hours_work_last_month,
        "hours_work_this_month": hours_work_this_month,
        "hours_quota": hours_quota,
        "current_session_work_hours": current_session_work_hours,
        "current_session": current_session,
        "unassigned_closed_session_hours": unassigned_closed_session_hours,
        "num_of_elapsed_workdays": num_of_elapsed_workdays,
        "num_of_workdays": num_of_workdays,
        "current_quota": current_quota,
        "quota_difference": quota_difference,
        "quota_difference_abs": quota_difference_abs,
        "avg_work_hours_fullfill_qoota": avg_work_hours_fullfill_quota,
        "workhours_per_day": WORKHOURS_PER_DAY,
        "hours_quota_last_month": hours_quota_last_month,
        "hours_quota_dif_last_month": hours_quota_dif_last_month,
    }
    return render(request, "attendance/user_page.html", context)

@login_required(login_url='/login/')
def sessions(request, username):
    if not user_check(request, username):
        return HttpResponse("Restricted to " + username)
    now =datetime.now()
    year_str = str(now.year)
    month_str = "{:02}".format(now.month)
    return HttpResponseRedirect(
            reverse(sessions_month, args=[request.user.username, year_str, month_str]))


@login_required(login_url='/login/')
def swipes(request, username):
    if not user_check(request, username):
        return HttpResponse("Restricted to " + username)
    swipes = Swipe.objects.filter(
            user__username = username,
            session__isnull = False,
    )

    context = {"swipes":swipes}
    return render(request, "attendance/swipes.html", context)

@login_required(login_url='/login/')
def sessions_month(request, username, year=datetime.now().year, month = datetime.now().month):
    if not user_check(request, username):
        return HttpResponse("Restricted to " + username)

    if request.method == "POST":
        form = ProjectSeparationForm(request.POST)
        if form.is_valid():
            form.save()
            url = reverse('sessions_month', kwargs={"username": username, "year": year, "month": month})
            return HttpResponseRedirect(url)

    in_swipes_ids = Swipe.objects.filter(
        swipe_type="IN",
        user__username=username,
        datetime__month=int(month),
        datetime__year=int(year),
    ).values_list('session', flat=True)
    sessions = Session.objects.filter(pk__in=in_swipes_ids)
    u = User.objects.get(username=username)

    separations = ProjectSeparation.objects.filter(session__in=sessions)

    form = ProjectSeparationForm()

    for session in sessions:
        session.form = ProjectSeparationForm(
                initial={
                        "time_spend": session.get_not_assigned_duration(),
                        "session": session.id  # hidden form
                },
        )

    projects = dict()

    for separation in separations:
        if separation.project.name in projects.keys():
            projects[separation.project.name] += separation.time_spend.seconds/3600
        else:
            projects[separation.project.name] = separation.time_spend.seconds/3600

    not_work_hours = Session.objects.get_not_work_hours_month(u, month, year)
    total_hours = Session.objects.get_hours_month(u.id, month, year)
    unassigned_hours = Session.objects.get_unassigned_hours_month(u.id, month, year)
    work_hours = total_hours - unassigned_hours - not_work_hours
    
    this_year = datetime.now().year
    chooseable_years = []
    for i in range(this_year, 2014, -1):
        chooseable_years.append(i)
    
    context = {
            "sessions": sessions,
            "year": year,
            "month": month,
            "total_hours": total_hours,
            "unassigned_hours": unassigned_hours,
            "work_hours": work_hours,
            "not_work_hours": not_work_hours,
            "list_of_projects": projects,
            "hours_quota": get_quota_work_hours(int(year), int(month), WORKHOURS_PER_DAY),
            "form": form,
            "chooseable_years": chooseable_years,
    }
    return render(request, "attendance/sessions.html", context)

@login_required(login_url='/login/')
def session_detail(request, username, id):
    if not user_check(request, username):
        return HttpResponse("Restricted to " + username)
    session = get_object_or_404(Session, pk = int(id))

    if session.user.username == username: #write test for this!!

        separations =  ProjectSeparation.objects.filter(session = session)
        swipes = Swipe.objects.filter(session = session)
        if request.method == "POST":
            form = ProjectSeparationForm(request.POST)
            if form.is_valid():
                form.save()
                url = reverse('session_detail', kwargs={"username": username, "id":id})
                return HttpResponseRedirect(url)

        form = ProjectSeparationForm(
                initial={
                        "time_spend":session.get_not_assigned_duration(),
                        "session": session.id #hidden form
                },
        )

        return_url = reverse("sessions_month", kwargs={
                'username': username,
                'year': str(session.get_date().year),
                'month': "{0:02d}".format(session.get_date().month, '02d'),
        })

        context = {
                "session":session,
                "id":id,
                "project_separation_form": form,
                "separations":separations,
                "swipes":swipes,
                "return_url": return_url,
        }
        return render(request, "attendance/session_detail.html", context)
    else:
        return HttpResponse("Restricted to " + session.user.username)

@login_required(login_url='/login/')
def swipe_detail(request, username, id):
    if not user_check(request, username):
        return HttpResponse("Restricted to " + username)
    swipe = get_object_or_404(Swipe, pk = int(id))

    if swipe.user.username == username: #write test for this!!

        if request.method == "POST":
            form = SwipeEditForm(request.POST, instance = swipe)

            if form.is_valid():
                cleaned_data = form.cleaned_data
                swipe.datetime = cleaned_data["datetime"]
                Swipe.objects.create(
                        user = swipe.user,
                        datetime = cleaned_data["datetime"],
                        swipe_type = swipe.swipe_type,
                        source = "Correction",
                        correction_of_swipe = swipe,
                )
        else:
            form = SwipeEditForm(
                    initial = {
                            "datetime":swipe.datetime,
                    }
            )
        if (swipe.swipe_set.all()):
            corrected_by = swipe.swipe_set.all()[0]
        else:
            corrected_by = None
        context={
                "swipe":swipe,
                "id": id,
                "form": form,
                "corrected_by": corrected_by
        }
        return render(request, "attendance/swipe_detail.html", context)
    else:
        return HttpResponse("Restricted to " + session.user.username)

@login_required(login_url='/login/')
def administrator(request, year=None, month=None, project=""):
    if year==None or month==None:
        return HttpResponseRedirect(reverse(administrator, args=[
                str(datetime.now().year),
                str("{0:02d}".format(datetime.now().month-1, '02d')),
        ]));
    if not (request.user.is_superuser or request.user.is_staff):
        return HttpResponse("Restricted to staff.")
    user_data, empty_users, projects_data = [], [], []

    users = User.objects.filter().prefetch_related(
        Prefetch(
            'session_set',
            queryset=Session.objects.filter(
                swipe__datetime__month=month,
                swipe__datetime__year=year,
                swipe__swipe_type="IN"
            ).prefetch_related("swipe_set").prefetch_related("projectseparation_set")
        )
    )

    for user in users:
        if user.session_set.all():
            user_data.append({
                    "user": user,
                    "hours_total": Session.objects.get_hours_month(user.id, month, int(year), sessions_month=user.session_set.all()),
                    "hours_unassigned": Session.objects.get_unassigned_hours_month(user.id, month, int(year), sessions_month=user.session_set.all()),
                    "hours_not_work": Session.objects.get_not_work_hours_month(user.id, month, int(year), sessions_month=user.session_set.all()),
                    "looks_ok": False,
                    "hours_work": 0
            })
        else:
            empty_users.append(user)

    for user in user_data:
        user["hours_work"] = user["hours_total"] - user["hours_unassigned"] - user["hours_not_work"]
        if user['hours_unassigned'] == 0 and user['hours_total'] > 0:
            user["looks_ok"] = True
        else:
            user["looks_ok"] = False

    locale.setlocale(locale.LC_ALL, "en_US.utf8")
    projects = Project.objects.all()
    separations =  ProjectSeparation.objects.filter(project__name = project).select_related("session").select_related("session__user").select_related("project")
    users = User.objects.all()

    all_users_month, all_users_overall = 0,0
    for user in users:
        duration, overall_duration = timedelta(0), timedelta(0)
        for sep in separations:
            if(sep.project.name == project and sep.session.user.username == user.username):
                overall_duration += sep.time_spend
                date = (sep.session.get_date())
                if('{:02d}'.format(date.month) == month and str(date.year) == year):
                    duration += sep.time_spend
        duration = timedelta_to_hours(duration)
        overall_duration = timedelta_to_hours(overall_duration)
        projects_data.append({
                "user": user,
                "hours": duration,
                "overall": overall_duration,
        })
        all_users_month += duration
        all_users_overall += overall_duration
    
    this_year = datetime.now().year
    chooseable_years = []
    for i in range(this_year, 2014, -1):
        chooseable_years.append(i)
    
    context = {
            "projects_data":projects_data,
            "project" : project,
            "projects": projects,
            "month": month,
            "year": year,
            "user_data": sorted(user_data, key=lambda dic: (locale.strxfrm(dic["user"].last_name))),
            "empty_users": sorted(empty_users, key=lambda user: (locale.strxfrm(user.last_name))),
            "all_users_month": all_users_month,
            "all_users_overall": all_users_overall,
            "chooseable_years": chooseable_years, 
    }
    if request.method == "POST":
        if request.POST.get("csv-UWS"): 
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="Hodoor administration report - users with sessions.csv"'

            field_names = ['Date: ' + str(datetime.now().date()),'Last name', 'First name', 'Username', 'Work hours', 'Not work hours',
                    'Hours unassigned', 'Hours total', 'Status']
            writer = csv.DictWriter(response, fieldnames=field_names)
            writer.writeheader()
            for user in user_data:
                if user["looks_ok"]:
                    status = "OK"
                else:
                    status = "not OK"
                writer.writerow({
                        "Username":user["user"].username,
                        "First name": user["user"].first_name,
                        "Last name": user["user"].last_name,
                        "Work hours": round(user["hours_work"], 3),
                        "Not work hours": round(user["hours_not_work"], 3),
                        "Hours unassigned": round(user["hours_unassigned"], 3),
                        "Hours total": round(user["hours_total"], 3),
                        "Status": status,
                })
        if request.POST.get("csv-UWNS"): 
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="Hodoor administration report - users without sessions.csv"'

            field_names = ['Date: ' + str(datetime.now().date()), 'Last name', 'First name', 'Username']
            writer = csv.DictWriter(response, fieldnames=field_names)
            writer.writeheader()
            for user in empty_users:
                writer.writerow({
                        "Username":user.username,
                        "First name": user.first_name,
                        "Last name": user.last_name,
                })
        if request.POST.get("xlsx"):
            response = make_administration_report(context) 
        return response
    return render(request, "attendance/administrator.html", context)

@login_required(login_url='/login/')
def generate_pdf(request, username, year=datetime.now().year, month = datetime.now().month):
    if not user_check(request, username):
        return HttpResponse("Restricted to " + username)

    user = User.objects.get(username=username)

    in_swipes_ids = Swipe.objects.filter(
        swipe_type="IN",
        user__username=username,
        datetime__month=int(month),
        datetime__year=int(year),
    ).values_list('session', flat=True)
    sessions = Session.objects.filter(pk__in=in_swipes_ids)
    sessions_and_holidays, days, dates = [], [], []

    for session in sessions:
        swipe_times = []
        projects = ""
        descriptions = ""
        separations =  ProjectSeparation.objects.filter(session = session)
        swipes = Swipe.objects.filter(session = session)

        for swipe in swipes:
            swipe_times.append(swipe.datetime)

        first = min(swipe_times)
        last = max(swipe_times)

        for sep in separations:
            projects += sep.project.name + "; "
            descriptions += sep.description + "; "
        sessions_and_holidays.append({
                    "date": session.get_date,
                    "day": session.get_date().day,
                    "duration": session.duration,
                    "entry": first,
                    "exit": last,
                    "projects": projects,
                    "descriptions": descriptions,
        })
    for i in range(1, monthrange(int(year),int(month))[1]+1):
        d = datetime (int(year), int(month), i)
        days.append({
            "day":i,
            "date": d,
        })

    context = {
        "user": user,
        "sessions_and_holidays": sessions_and_holidays,
        "days" : days,
        "year" : year,
        "month" : month,
        "dates" : dates,
    }

    # Rendered
    html_string = render_to_string('attendance/work_report_pdf.html', context)
    html = HTML(string=html_string)
    result = html.write_pdf()


    http_response = HttpResponse(result, content_type='attendance/work_report_pdf.html')
    http_response['Content-Disposition'] = 'filename='+user.first_name+'_'+user.last_name+'_'+year+'/'+month+'.pdf'

    return http_response
