from flask import Blueprint, render_template

main = Blueprint('main', __name__)

@main.route('/')
def index():
    """Rota para a página inicial"""
    return render_template('home.html')
