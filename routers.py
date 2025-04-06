from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, jsonify

from models import DatabaseManager

db_manager = DatabaseManager()

main_blueprint = Blueprint('main', __name__)
user_blueprint = Blueprint('user', __name__)
trip_blueprint = Blueprint('trip', __name__)


@main_blueprint.route('/')
def hello():
    return render_template('hello.html')


@user_blueprint.route('/')
def user_list():
    users = db_manager.get_all_users()
    return render_template('user_list.html', users=users)


@user_blueprint.route('/create', methods=['POST'])
def create_user():
    username = request.form.get('username')
    email = request.form.get('email')

    if username and email:
        flag = db_manager.create_user(username, email)
        if not flag:
            return "Username or email occupied", 400
    return redirect(url_for('user.user_list'))


@user_blueprint.route('/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    flag = db_manager.delete_user(user_id)
    if not flag:
        return "User_id not exist", 404
    return redirect(url_for('user.user_list'))


@trip_blueprint.route('/')
def trip_list():
    trips = db_manager.get_all_trips()
    users = db_manager.get_all_users()
    return render_template('trip_list.html', trips=trips, users=users)


@trip_blueprint.route('/create', methods=['POST'])
def create_trip():
    try:
        start_day = datetime.strptime(request.form['start_day'], '%Y-%m-%d').date()
        end_day = datetime.strptime(request.form['end_day'], '%Y-%m-%d').date()
        participants = list(map(int, request.form.getlist('participants')))
        
        if start_day >= end_day:
            raise ValueError("End date must be after start date")
            
        trip_id = db_manager.create_trip(participants, start_day.isoformat(), end_day.isoformat())
        return redirect(url_for('trip.trip_list'))
    
    except Exception as e:
        return str(e), 400


@trip_blueprint.route('/delete/<int:trip_id>', methods=['POST'])
def delete_trip(trip_id):
    flag = db_manager.delete_trip(trip_id)
    if not flag:
        return "Trip_id not exist", 404
    return redirect(url_for('trip.trip_list'))
