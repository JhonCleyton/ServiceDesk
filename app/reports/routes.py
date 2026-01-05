from flask import Blueprint, render_template, Response, request
from flask_login import login_required
from ..models import Ticket
import csv
import io
from datetime import datetime, timedelta


reports_bp = Blueprint('reports', __name__, template_folder='../templates')


@reports_bp.route('/')
@login_required
def index():
    period = request.args.get('period', 'all')  # all|today|week|month
    now = datetime.utcnow()
    start = None
    if period == 'today':
        start = now - timedelta(days=1)
    elif period == 'week':
        start = now - timedelta(days=7)
    elif period == 'month':
        start = now - timedelta(days=30)

    q = Ticket.query
    if start is not None:
        q = q.filter(Ticket.created_at >= start)
    tickets = q.all()
    total = len(tickets)
    by_status = {}
    by_priority = {}
    by_company = {}
    rating_sum_by_company = {}
    rating_count_by_company = {}
    rating_sum_all = 0
    rating_count_all = 0
    for t in tickets:
        by_status[t.status] = by_status.get(t.status, 0) + 1
        by_priority[t.priority] = by_priority.get(t.priority, 0) + 1
        company_name = t.company.name if getattr(t, 'company', None) else '—'
        by_company[company_name] = by_company.get(company_name, 0) + 1
        if t.user_rating is not None:
            rating_sum_by_company[company_name] = rating_sum_by_company.get(company_name, 0) + (t.user_rating or 0)
            rating_count_by_company[company_name] = rating_count_by_company.get(company_name, 0) + 1
            rating_sum_all += t.user_rating or 0
            rating_count_all += 1
    avg_overall = (rating_sum_all / rating_count_all) if rating_count_all else None
    ratings_by_company = {}
    for cname, cnt in rating_count_by_company.items():
        ratings_by_company[cname] = {
            'avg': (rating_sum_by_company.get(cname, 0) / cnt) if cnt else None,
            'count': cnt,
        }
    recent_ratings = [t for t in tickets if t.user_rating_at is not None and (start is None or t.user_rating_at >= start)]
    recent_ratings.sort(key=lambda x: x.user_rating_at, reverse=True)
    recent_ratings = recent_ratings[:10]

    # Prepare chart data: company ratings (avg) arrays
    company_labels = []
    company_avgs = []
    for cname in sorted(by_company.keys()):
        company_labels.append(cname)
        r = ratings_by_company.get(cname)
        company_avgs.append(round(r['avg'], 2) if r and r.get('avg') is not None else 0)

    # Trend by day: average rating per day within period
    trend = {}
    for t in tickets:
        if t.user_rating_at is None:
            continue
        if start is not None and t.user_rating_at < start:
            continue
        day = t.user_rating_at.strftime('%Y-%m-%d')
        if day not in trend:
            trend[day] = {'sum': 0, 'count': 0}
        trend[day]['sum'] += t.user_rating or 0
        trend[day]['count'] += 1
    trend_labels = sorted(trend.keys())
    trend_avgs = [round(trend[d]['sum'] / trend[d]['count'], 2) if trend[d]['count'] else 0 for d in trend_labels]

    return render_template(
        'reports/index.html',
        total=total,
        by_status=by_status,
        by_priority=by_priority,
        by_company=by_company,
        avg_overall=avg_overall,
        ratings_by_company=ratings_by_company,
        recent_ratings=recent_ratings,
        company_labels=company_labels,
        company_avgs=company_avgs,
        trend_labels=trend_labels,
        trend_avgs=trend_avgs,
        period=period,
    )


@reports_bp.route('/export.csv')
@login_required
def export_csv():
    period = request.args.get('period', 'all')
    now = datetime.utcnow()
    start = None
    if period == 'today':
        start = now - timedelta(days=1)
    elif period == 'week':
        start = now - timedelta(days=7)
    elif period == 'month':
        start = now - timedelta(days=30)
    q = Ticket.query
    if start is not None:
        q = q.filter(Ticket.created_at >= start)
    tickets = q.all()
    proxy = io.StringIO()
    writer = csv.writer(proxy)
    writer.writerow(['number','title','status','priority','company','created_at','due_first_response_at','first_response_at','due_resolution_at','resolved_at','closed_at','user_rating','user_rating_comment','user_rating_at'])
    for t in tickets:
        writer.writerow([
            t.number,
            t.title,
            t.status,
            t.priority,
            t.company.name if getattr(t, 'company', None) else '',
            t.created_at.isoformat() if t.created_at else '',
            t.due_first_response_at.isoformat() if t.due_first_response_at else '',
            t.first_response_at.isoformat() if t.first_response_at else '',
            t.due_resolution_at.isoformat() if t.due_resolution_at else '',
            t.resolved_at.isoformat() if t.resolved_at else '',
            t.closed_at.isoformat() if t.closed_at else '',
            t.user_rating if t.user_rating is not None else '',
            (t.user_rating_comment or '').replace('\n', ' ').strip() if t.user_rating_comment else '',
            t.user_rating_at.isoformat() if t.user_rating_at else '',
        ])
    mem = io.BytesIO()
    mem.write(proxy.getvalue().encode('utf-8'))
    mem.seek(0)
    proxy.close()
    return Response(mem, mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename="tickets.csv"'})
