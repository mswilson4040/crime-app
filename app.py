from flask import Flask, render_template, redirect, url_for, request, session, jsonify, send_from_directory
from models import db, User, Case, Report, Predictive, Favorite
from passlib.hash import sha256_crypt
from forms import LoginForm, SignupForm
import simplejson as json
from sqlalchemy import func

app = Flask(__name__)
app.secret_key = 'shhhhitsasecret'

app.config[
    'SQLALCHEMY_DATABASE_URI'] = 'postgres://rfacbcjizycwdl:58ec71e5deca626dea647631b65719669587a5b56f69c6b7072dceeeda368d29@ec2-50-17-203-51.compute-1.amazonaws.com:5432/dmiofp34d7sht';
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


# General Redirect
@app.route('/')
def redir():
    return redirect(url_for('index'))


# Index
@app.route('/index')
def index():
    # TODO: Cache this stuff. No need to make the call on every page load
    yearOptions = db.session.query(Case.year).distinct().all()
    yearOptions = sorted([y[0] for y in yearOptions])

    typeOptions = db.session.query(Case.primary_type).distinct().all()
    typeOptions = sorted(t[0] for t in typeOptions)

    districtOptions = db.session.query(Case.district).distinct().all()
    districtOptions = sorted(d[0] for d in districtOptions)

    if 'username' in session:
        user = User.query.filter_by(username=session['username']).first()
        return render_template('index.html', title='Home', session_username=user.username, yearOptions=yearOptions, typeOptions=typeOptions, districtOptions=districtOptions)
    else:
        return render_template('index.html', title='Home', yearOptions=yearOptions, typeOptions=typeOptions, districtOptions=districtOptions)


# Signup
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            # TODO: Username already exists. Do something meaninful
            return redirect(url_for('signup'))
        else:
            user = User(username=username, password=sha256_crypt.hash(password))
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('index'))
    else:
        return render_template('signup.html', title="Sign Up")


# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user is None:
            flash('Email is required')
            return redirect(url_for('login'))
        elif sha256_crypt.verify(password, user.password):
            session['username'] = user.username
            return redirect(url_for('index'))
        else:
            # TODO: Invalid Credentials
            flash('Invalid login')
            return redirect(url_for('login'))
    else:
        return render_template('login.html', title="Log In", form=LoginForm())


# Logout
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('index'))

# Save current filters
@app.route('/save', methods=['POST'])
def save():
    if request.method == 'POST':
        typeFilter = request.form['type']
        yearFilter = request.form['year']
        districtFilter = request.form['district']
        user = User.query.filter_by(username=session['username']).first()

        report = Report()
        report.uid = user.uid
        if typeFilter:
            report.type = typeFilter
        if yearFilter and yearFilter.isdigit():
            report.year = int(yearFilter)
        if districtFilter and districtFilter.isdigit():
            report.district = int(districtFilter)

        # report = Report(type=typeFilter, year=int(yearFilter), district=int(districtFilter), uid=user.uid)
        db.session.add(report)
        db.session.commit()
        flash('Report saved!')
    return jsonify( { 'result': True } )


# Delete Report
@app.route('/delete/<rid>', methods=['POST'])
def delete_report(rid):
    user = User.query.filter_by(username=session['username']).first()
    Report.query.filter_by(uid=user.uid, rid=rid).delete()
    db.session.commit()
    return redirect(url_for('saved_reports'))


# Saved Reports
@app.route('/saved-reports', methods=['GET', 'POST'])
def saved_reports():
    if request.method == 'GET':
        user = User.query.filter_by(username=session['username']).first()
        saved_reports = Report.query.filter_by(uid=user.uid).all()
        
        relationships = Favorite.query.filter_by(uid=user.uid).all()
        cids_favorited = [f.cid for f in relationships]
        favorited_reports = Case.query.filter(Case.id.in_(cids_favorited)).all()

        return render_template('saved-reports.html', title="Saved Reports", saved_reports=saved_reports, favorited_reports=favorited_reports, session_username=user.username)


# Forecast
@app.route('/forecast', methods=['GET'])
def forecast():
	if request.method == 'GET':
		if 'username' in session:
			user = User.query.filter_by(username=session['username']).first()
			return render_template('forecast.html', title='Forecast', session_username=user.username)

		return render_template('forecast.html', title='Forecast')

# Favorite from details page
@app.route('/favorite/<cid>', methods=['POST'])
def favorite(cid):
	session_user = User.query.filter_by(username=session['username']).first()
	case_to_favorite = Case.query.filter_by(id=cid).first()

	new_favorite = Favorite(uid=session_user.uid, cid=case_to_favorite.id)
	new_url = "/detail?id="+str(case_to_favorite.id)

	db.session.add(new_favorite)
	db.session.commit()
	return redirect(new_url)

# Unfavorite from details page
@app.route('/unfavorite/<cid>/<from_url>', methods=['POST'])
def unfavorite(cid, from_url):
	session_user = User.query.filter_by(username=session['username']).first()
	case_to_unfavorite = Case.query.filter_by(id=cid).first()

	delete_favorite = Favorite.query.filter_by(uid=session_user.uid, cid=case_to_unfavorite.id).first()

	db.session.delete(delete_favorite)
	db.session.commit()

	if from_url == "saved_reports":
		return redirect(url_for('saved_reports'))
	else:
		new_url = "/detail?id="+str(case_to_unfavorite.id)
		return redirect(new_url)


# Details
@app.route('/detail')
def detail():
	if 'username' in session:
		user = User.query.filter_by(username=session['username']).first()
		case = request.args.get('id')
		if Favorite.query.filter_by(uid=user.uid, cid=case).first():
			favorited = True
		else:
			favorited = False
		return render_template('detail.html', title='Details', session_username=user.username, favorited=favorited, case=case)
	return render_template('detail.html', title='Details', favorited=False)



############# API ENDPOINTS #############

# Get Crimes By Year
@app.route('/api/breakdown/year')
def crimes_by_year():
    primary_type = request.args.get('type')
    district = request.args.get('district')
    query = db.session.query(Case.year, func.count(Case.id)).group_by(Case.year)
    filters = []
    if primary_type:
        filters.append(Case.primary_type == primary_type)
    if district and district.isdigit():
        filters.append(Case.district == int(district))
    query = query.filter(*filters)
    breakdown = query.all()
    ret = []
    for b in breakdown:
        ret.append({
            'year': int(b[0]),
            'count': int(b[1])
        })
    return jsonify(ret)


# Get Crimes by Type
@app.route('/api/breakdown/type')
def crimes_by_type():
    year = request.args.get('year')
    district = request.args.get('district')
    filters = []
    query = db.session.query(Case.primary_type, func.count(Case.id)).group_by(Case.primary_type)
    if year and year.isdigit():
        filters.append(Case.year == int(year))
    if district and district.isdigit():
        filters.append(Case.district == int(district))
    query = query.filter(*filters)
    breakdown = query.all()
    ret = []
    for b in breakdown:
        ret.append({
            'type': b[0],
            'count': int(b[1])
        })
    return jsonify(ret)


# Get Crimes by District
@app.route('/api/breakdown/district')
def crimes_by_district():
    year = request.args.get('year')
    primary_type = request.args.get('type')
    query = db.session.query(Case.district, func.count(Case.id)).group_by(Case.district)
    filters = []
    if year and year.isdigit():
        filters.append(Case.year == int(year))
    if primary_type:
        filters.append(Case.primary_type == primary_type)
    query = query.filter(*filters)
    breakdown = query.all()
    ret = []
    for b in breakdown:
        ret.append({
            'district': int(b[0]),
            'count': int(b[1])
        })
    return jsonify(ret)


# Get Dataset
@app.route('/api/data')
def get_dataset():
    year = request.args.get('year')
    primary_type = request.args.get('type')
    district = request.args.get('district')
    filters = []
    query = db.session.query(Case).order_by(Case.date)
    if year and year.isdigit():
        filters.append(Case.year == int(year))
    if primary_type:
        filters.append(Case.primary_type == primary_type)
    if district and district.isdigit():
        filters.append(Case.district == int(district))
    query = query.filter(*filters).limit(100)
    dataset = query.all()
    ret = []
    for c in dataset:
        ret.append(c.to_json())
    return jsonify(ret)


# Get Crime by Id
@app.route('/api/cases/<id>')
def get_case_by_id(id):
    if id:
        crime = Case.query.filter_by(id=int(id)).first()
        return jsonify(crime.to_json())


# Chicago Json
@app.route('/api/chicago')
def get_chicago():
    return send_from_directory('static/data', 'chicago.json')


# Predictive Json
@app.route('/api/predictive')
def get_predictive():
    #dataset = Predictive.query.limit(100).all()
    dataset = Predictive.query.order_by(Predictive.id.desc()).limit(312).all()
    dataset = dataset[::-1]
    ret = []
    for c in dataset:
        ret.append(c.to_json())
    return jsonify(ret)


if __name__ == '__main__':
    app.run()
