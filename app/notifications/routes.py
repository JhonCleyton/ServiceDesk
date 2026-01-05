from flask import Blueprint, jsonify, request, Response, stream_with_context
from flask_login import login_required, current_user
from datetime import datetime
from ..models import Notification
from .. import db
import json
import time

notify_bp = Blueprint('notify', __name__)


@notify_bp.route('/notify/poll')
@login_required
def poll():
    after_id = request.args.get('after_id', type=int)
    base = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.id.desc())
    if after_id:
        q = base.filter(Notification.id > after_id)
    else:
        # Primeira carga: só trazer não vistas para evitar repetir toasts a cada refresh
        q = base.filter(Notification.seen_at == None)  # type: ignore
    items = q.limit(20).all()
    unread = Notification.query.filter_by(user_id=current_user.id, read_at=None).count()
    data = [
        {
            'id': n.id,
            'title': n.title,
            'body': n.body or '',
            'link': n.link or '',
            'created_at': n.created_at.isoformat() if n.created_at else None,
        }
        for n in items
    ]
    # mark delivered (seen)
    now = datetime.utcnow()
    for n in items:
        if not n.seen_at:
            n.seen_at = now
    db.session.commit()
    return jsonify({'ok': True, 'unread': unread, 'items': data})


@notify_bp.route('/notify/seen', methods=['POST'])
@login_required
def mark_seen():
    now = datetime.utcnow()
    Notification.query.filter_by(user_id=current_user.id, seen_at=None).update({'seen_at': now})
    db.session.commit()
    return jsonify({'ok': True})


@notify_bp.route('/notify/stream')
@login_required
def stream():
    after_id = request.args.get('after_id', type=int) or 0
    def gen():
        last = after_id
        for _ in range(600):  # ~50 min @5s
            base = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.id.desc())
            if last:
                q = base.filter(Notification.id > last)
            else:
                # Primeira conexão: apenas não vistas
                q = base.filter(Notification.seen_at == None)  # type: ignore
            items = q.limit(20).all()
            unread = Notification.query.filter_by(user_id=current_user.id, read_at=None).count()
            data = [{
                'id': n.id,
                'title': n.title,
                'body': n.body or '',
                'link': n.link or '',
                'created_at': n.created_at.isoformat() if n.created_at else None,
            } for n in items]
            if items:
                last = max(last, max(n.id for n in items))
                now = datetime.utcnow()
                for n in items:
                    if not n.seen_at:
                        n.seen_at = now
                db.session.commit()
            payload = json.dumps({'unread': unread, 'items': data})
            yield f"data: {payload}\n\n"
            time.sleep(5)
    return Response(stream_with_context(gen()), mimetype='text/event-stream')


@notify_bp.route('/notify/read_all', methods=['POST'])
@login_required
def mark_all_read():
    from datetime import datetime
    now = datetime.utcnow()
    Notification.query.filter_by(user_id=current_user.id).update({'read_at': now, 'seen_at': now})
    db.session.commit()
    return jsonify({'ok': True})


@notify_bp.route('/notify/read/<int:nid>', methods=['POST'])
@login_required
def mark_read(nid):
    n = Notification.query.filter_by(id=nid, user_id=current_user.id).first_or_404()
    now = datetime.utcnow()
    n.read_at = now
    if not n.seen_at:
        n.seen_at = now
    db.session.commit()
    return jsonify({'ok': True})
