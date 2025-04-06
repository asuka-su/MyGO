from flask import Blueprint, render_template, request, redirect, url_for
from models import DatabaseManager

db_manager = DatabaseManager()

main_blueprint = Blueprint('main', __name__)
user_blueprint = Blueprint('user', __name__)

@main_blueprint.route('/')
def hello():
    return render_template('hello.html')

@user_blueprint.route('/')
def user_list():
    users = db_manager.get_all_users()
    return render_template('user_list.html', users=users)

@user_blueprint.route('/add', methods=['POST'])
def add_user():
    username = request.form.get('username')
    email = request.form.get('email')

    if username and email:
        flag = db_manager.add_user(username, email)
        if not flag:
            return "Username or email occupied", 400
    return redirect(url_for('user.user_list'))

@user_blueprint.route('/delete/<int:user_id>')
def delete_user(user_id):
    flag = db_manager.delete_user(user_id)
    if not flag:
        return "User_id not exist", 404
    return redirect(url_for('user.user_list'))