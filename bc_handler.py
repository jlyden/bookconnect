# Book Connect Handler
#
# These are the functions needed to run the BookConnect website
#
# Written by jennifer lyden for Harvard University's CS50
# with support from the Full Stack Nanodegree courses at Udacity


from flask import Flask, render_template, url_for, request, redirect, flash, jsonify, make_response
from flask import session as login_session
from flask.ext.mail import Mail, Message
from sqlalchemy import create_engine, literal
from sqlalchemy.orm import sessionmaker
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import datetime, random, string, httplib2, json, requests
from datetime import date, timedelta
from bc_db_setup import Base, Users, Books


app = Flask(__name__)

# Credit to snippet - http://flask.pocoo.org/snippets/85/
app.config.update(
    DEBUG=True,
    #Email settings
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
#    MAIL_PORT=465,
#    MAIL_USE_SSL=True,
    MAIL_USERNAME = 'BookConnectBot@gmail.com',
    MAIL_PASSWORD = 'CS50BookConnect'
)

mail = Mail(app)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Book Connect"

# Database connection setup
engine = create_engine('sqlite:///bookconnect.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()


# Create anti-forgery state token stored in session for later validation.
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


# Google login functions
@app.route('/gconnect', methods=['POST'])
def gconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    code = request.data

    # Upgrade auth code into credentials object
    try:
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check access token is valid
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s' % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    print result
    # If there was error in access token info, abort
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')),500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify intended user presented access token
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify access token valid for this app
    if result['issued_to'] != '195477151614-j6h8p2s4j2k7cj5bgfto78r8qvd9srfp.apps.googleusercontent.com':
        response = make_response(json.dumps("Token's client ID doesn't match app's."), 401)
        print "Token's client ID doesn't match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    # If all those tests passed ...
    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store access token in session for later use
    login_session['credentials'] = access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)
    data = answer.json()

    login_session['provider'] = 'google'
    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # Check if user exists in Database
    email = login_session['email']
    user_id = getUserID(email)
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += '" style = "width: 300px; height: 300px; border-radius: 150px; -webkit-border-radius: 150px; -moz-border-radius: 150px;">'
    flash("You are now logged in as %s" % login_session['username'])
    print "done!"
    return output

# Google disconnect - revoke user's token
@app.route('/gdisconnect')
def gdisconnect():
    # Only disconnect a connected user
    access_token = login_session.get('credentials')
#    print 'access_token is %s', access_token
#    print 'username is:'
#    print login_session['username']
    if access_token is None:
        response = make_response(json.dumps('User not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Execute HTTP GET request to revoke token
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] == '200':
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        # For some reason, token was invalid.
        response = make_response(json.dumps('Failed to revoke token for given user.'), 400)
        response.headers['Content-Type'] = 'application/json'
        return response


# Facebook connect
@app.route('/fbconnect', methods=['POST'])
def fbconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = request.data
    print "access token received %s " % access_token

    # Exchange client token for long-lived server-side token
    app_id = json.loads(open('fb_client_secrets.json', 'r').read())['web']['app_id']
    app_secret = json.loads(open('fb_client_secrets.json', 'r').read())['web']['app_secret']
    url = 'https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=%s&client_secret=%s&fb_exchange_token=%s' % (app_id, app_secret, access_token)
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]

    # Use token to get user info from API
    userinfo_url = "https://graph.facebook.com/v2.4/me"
    # strip expire tag from access token
    token = result.split("&")[0]

    url = 'https://graph.facebook.com/v2.4/me?%s&fields=name,id,email' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    print "url sent for API access: %s" % url
    print "API JSON result: %s" % result
    data = json.loads(result)

    login_session['provider'] = 'facebook'
    login_session['username'] = data["name"]
    login_session['email'] = data["email"]
    login_session['facebook_id'] = data["id"]

    # store access token for later logout
    stored_token = token.split("=")[1]
    login_session['access_token'] = stored_token

    # Get user picture
    url = 'https://graph.facebook.com/v2.4/me/picture?%s&redirect=0&height=200&width=200' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    data = json.loads(result)
    login_session['picture'] = data["data"]["url"]

    # Check if user exists in Database
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += '" style = "width: 300px; height: 300px; border-radius: 150px; -webkit-border-radius: 150px; -moz-border-radius: 150px;">'
    flash("You are now logged in as %s" % login_session['username'])
    print "done!"
    return output


# Facebook disconnect
@app.route('/fbdisconnect')
def fbdisconnect():
    facebook_id = login_session['facebook_id']
    url = 'https://graph.facebook.com/%s/permissions' % facebook_id
    h = httplib2.Http()
    result = h.request(url, 'DELETE')[1]
    return "You have been logged out."


# Any provider disconnect - calls helper function to revoke access token and resets login_session
@app.route('/disconnect')
def disconnect():
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
            del login_session['gplus_id']
            del login_session['credentials']
        if login_session['provider'] == 'facebook':
            fbdisconnect()
            del login_session['facebook_id']

        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        flash("You have successfully logged out.")
        return redirect(url_for('index'))
    else:
        flash("You were not logged in!")
        return redirect(url_for('index'))


# recent books query - Index
@app.route('/')
@app.route('/index')
def index():
    today = date.today()
    sixMo = today - datetime.timedelta(183)
    items = session.query(Books).\
                    filter(Books.date >= sixMo).\
                    order_by(Books.course).all()
    if not items:
        return render_template('recentsNo.html')
    else:
        return render_template('recentsYes.html', items = items)


# Render About page
@app.route('/about', methods=['GET', 'POST'])
def about():
    if request.method == 'POST':
        # Input code to send e-mail TO the Bot.
        flash('Your comments have been forwarded to admin.')
        return redirect(url_for('index'))
    else:
        return render_template('about.html')



# books by user query - Inventory
@app.route('/inventory')
def inventory():
    if 'username' not in login_session:
        flash('Please sign in first ...')
        return redirect(url_for('showLogin'))
    else:
        user_id = login_session['user_id']
        items = session.query(Books).\
                        filter_by(user_id = user_id).\
                        order_by(Books.course).all()
        if not items:
            return render_template('inventoryNo.html')
        else:
            return render_template('inventoryYes.html', items = items)


# search
@app.route('/books/search', methods=['GET', 'POST'])
def enquiry():
    if request.method == 'POST':
        courseNum = courseParser(request.form['courseNum'])
        items = session.query(Books).\
                        filter_by(course = courseNum).\
                        order_by(Books.name).all()
        if not items:
            return render_template('resultsNo.html')
        else:
            return render_template('resultsYes.html', items = items)
    else:
        return render_template('search.html')


# connect
@app.route('/books/<int:book_id>/connect', methods=['GET', 'POST'])
def connect(book_id):
    if 'username' not in login_session:
        flash('Please sign in first ...')
        return redirect(url_for('showLogin'))
    thisBook = session.query(Books).\
                    filter_by(id = book_id).first()
    if request.method == 'POST':
        buyer = getUserInfo(login_session['user_id'])
        seller = getUserInfo(thisBook.user_id)
#       Mail disabled for now because of SMTP Auth errors from Google
#        sendMail(buyer.email, seller.email, thisBook.name)
        return render_template('connect.html', book_id=book_id, book = thisBook)
    else:
        return render_template('found.html', book = thisBook, book_id=book_id)


# create new book
@app.route('/books/new', methods=['GET', 'POST'])
def newBook():
    if 'username' not in login_session:
        flash('Please sign in first ...')
        return redirect(url_for('showLogin'))
    if request.method == 'POST':
        course = courseParser(request.form['course'])
        price = priceParser(request.form['bookPrice'])
        newBook = Books(name = request.form['bookName'], \
                        date = date.today(), \
                        ISBN = request.form['bookISBN'], \
                        course = course, \
                        price = price, \
                        user_id=login_session['user_id'])
        session.add(newBook)
        session.commit()
        flash("New book added!")
        return redirect(url_for('inventory'))
    else:
        return render_template('bookNew.html')


# edit book
#@app.route('/books/<int:user_id>/<int:book_id>/edit/', methods=['GET', 'POST'])
@app.route('/books/<int:book_id>/edit', methods=['GET', 'POST'])
def editBook(book_id):
    if 'username' not in login_session:
        flash('Please sign in first ...')
        return redirect(url_for('showLogin'))
    thisBook = session.query(Books).filter_by(id = book_id).one()
    if thisBook.user_id != login_session['user_id']:
        flash('You do not have permission to edit %s' % thisBook.name)
        return redirect(url_for('index'))
    if request.method == 'POST':
        if request.form['bookName']:
            thisBook.name = request.form['bookName']
        if request.form['bookISBN']:
            thisBook.ISBN = request.form['bookISBN']
        if request.form['course']:
            thisBook.course = request.form['bookISBN']
        if request.form['bookPrice']:
            thisBook.price = request.form['bookPrice']
        session.add(thisBook)
        session.commit()
        flash("Book edited!")
        return redirect(url_for('inventory'))
    else:
        return render_template('bookEdit.html', book_id = book_id, book = thisBook)


# delete book
@app.route('/books/<int:book_id>/delete', methods=['GET', 'POST'])
def deleteBook(book_id):
    if 'username' not in login_session:
        flash('Please sign in first ...')
        return redirect(url_for('showLogin'))
    thisBook = session.query(Books).filter_by(id = book_id).one()
    if thisBook.user_id != login_session['user_id']:
        flash('You do not have permission to edit %s' % thisBook.name)
        return redirect(url_for('index'))
    if request.method == 'POST':
        session.delete(thisBook)
        session.commit()
        flash("Book removed from system.")
        return redirect(url_for('inventory'))
    else:
        return render_template('bookDelete.html', book_id = book_id, book = thisBook)


# Send mail message for connect
def sendMail(emailBuyer, emailSeller, bookName):
    msg = Message(
            "%s, a fellow BookConnect user, is interested in buying your copy of %s. Please contact this user at %s. Don't forget to DELETE the book from your BookConnect inventory once you have sold it. Thanks!" % (login_session['username'], bookName, emailBuyer),
            sender = 'BookConnectBot@gmail.com',
            recipients = [emailSeller])
    msg.subject = "Someone wants your book!"
    mail.send(msg)
    return


# get user ID using email (duh)
def getUserID(email):
    try:
        user = session.query(Users).filter_by(email = email).one()
        return user.id
    except:
        return None


# get user info using user_id (duh)
def getUserInfo(user_id):
    user = session.query(Users).filter_by(id = user_id).one()
    return user


# Create user based on login session data
def createUser(login_session):
    newUser = Users(name = login_session['username'], email = login_session['email'], picture = login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(Users).filter_by(email = login_session['email']).one()
    return user.id


# Helper function for course number parsing
def courseParser(courseNumber):
    if "-" not in courseNumber:
        return courseNumber
    lhs, rhs = courseNumber.split("-", 1)
    upLHS = lhs.upper()
    cleanNumber = upLHS + "-" + rhs
    return cleanNumber


# Helper function for price parsing
def priceParser(oldPrice):
    if "$" not in oldPrice:
        return oldPrice
    cleanPrice = oldPrice.replace("$", "")
    return cleanPrice

# delete user
#@app.route('/books/<int:user_id>/delete/', methods=['GET', 'POST'])
#def deleteUser(user_id):
#    thisUser = session.query(Users).filter_by(id = user_id).one()
#    if request.method == 'POST':
#        session.delete(thisUser)
#        session.commit()
#        flash("User removed from system.")
#        return redirect(url_for('index', user_id = user_id))
#    else:
#        return render_template('deleteuser.html', user_id = user_id, item #= thisUser)


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host = '0.0.0.0', port = 5000)
