from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.secret_key = "supersecret"  # session için gerekli
db = SQLAlchemy(app)

class Title(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(50), nullable=True)  # şifreli oda için

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('title.id'), nullable=False)
    username = db.Column(db.String(50), nullable=False)
    text = db.Column(db.String(200), nullable=True)
    gif = db.Column(db.String(200), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

@app.route('/')
def index():
    titles = Title.query.all()
    room_data = []
    for t in titles:
        msg_count = Message.query.filter_by(room_id=t.id).count()
        room_data.append({"id": t.id, "name": t.name, "count": msg_count, "locked": bool(t.password)})
    return render_template('index.html', rooms=room_data)

@app.route('/setname', methods=['POST'])
def setname():
    session['username'] = request.form['username']
    return redirect('/')

@app.route('/create', methods=['POST'])
def create():
    title_name = request.form['title']
    room_type = request.form['room_type']
    password = request.form.get('password') if room_type == "locked" else None

    if room_type == "locked" and not password:
        return "Şifreli oda için şifre girmeniz gerekiyor!"

    new_title = Title(name=title_name, password=password)
    db.session.add(new_title)
    db.session.commit()
    return redirect('/')

@app.route('/chat/<int:room_id>', methods=['GET', 'POST'])
def chat(room_id):
    room = Title.query.get_or_404(room_id)

    # Şifreli oda kontrolü
    if room.password:
        if session.get(f"room_{room_id}_access"):
            messages = Message.query.filter_by(room_id=room.id).all()
            return render_template('chat.html', room=room, messages=messages, username=session.get('username'))

        if request.method == 'POST':
            entered_password = request.form['password']
            if entered_password == room.password:
                session[f"room_{room_id}_access"] = True
                messages = Message.query.filter_by(room_id=room.id).all()
                return render_template('chat.html', room=room, messages=messages, username=session.get('username'))
            else:
                return render_template('password.html', room=room, error="Yanlış şifre!")

        return render_template('password.html', room=room)

    # Şifresiz oda
    messages = Message.query.filter_by(room_id=room.id).all()
    return render_template('chat.html', room=room, messages=messages, username=session.get('username'))

@app.route('/send', methods=['POST'])
def send():
    room_id = request.form['room_id']
    username = session.get('username', "Anonim")
    text = request.form.get('text')
    gif_url = request.form.get('gif_url')
    msg = Message(room_id=room_id, username=username, text=text, gif=gif_url)
    db.session.add(msg)
    db.session.commit()
    return redirect(f'/chat/{room_id}')

@app.route('/delete', methods=['POST'])
def delete():
    room_name = request.form['room_name']
    room = Title.query.filter_by(name=room_name).first()
    if not room:
        return f"Böyle bir oda yok: {room_name}"
    Message.query.filter_by(room_id=room.id).delete()
    db.session.delete(room)
    db.session.commit()
    return redirect('/')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

from flask_socketio import SocketIO, emit, join_room

socketio = SocketIO(app)

@socketio.on('join')
def handle_join(data):
    room_id = str(data['room_id'])
    join_room(room_id)

@socketio.on('typing')
def handle_typing(data):
    username = data['username']
    room_id = str(data['room_id'])
    # Odaya yayın yapıyoruz
    emit('show_typing', {'username': username}, room=room_id, include_self=False)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True)
