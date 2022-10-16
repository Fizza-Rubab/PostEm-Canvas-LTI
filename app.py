from flask import Flask, render_template, session, request, Response, send_file,url_for
from pylti.flask import lti
import settings
import pandas as pd
import logging
import json
from logging.handlers import RotatingFileHandler
import os
from tempfile import NamedTemporaryFile
import shutil
import csv

app = Flask(__name__)
app.secret_key = settings.secret_key
app.config.from_object(settings.configClass)


# ============================================
# Logging
# ============================================

formatter = logging.Formatter(settings.LOG_FORMAT)
handler = RotatingFileHandler(
    settings.LOG_FILE,
    maxBytes=settings.LOG_MAX_BYTES,
    backupCount=settings.LOG_BACKUP_COUNT
)
handler.setLevel(logging.getLevelName(settings.LOG_LEVEL))
handler.setFormatter(formatter)
app.logger.addHandler(handler)


# ============================================
# Utility Functions
# ============================================

def return_error(msg):
    return render_template('error.html', msg=msg)


def error(exception=None):
    app.logger.error("PyLTI error: {}".format(exception))
    return return_error('''Authentication error,
        please refresh and try again. If this error persists,
        please contact support.''')

def getCSVFilename(assign, course):
    file = open("/home/Fizzaa39/"+ course + "/mapping.csv")
    csvreader = csv.reader(file)
    data = []
    header = []
    header = next(csvreader)
    for row in csvreader:
        if row[0]==assign:
            return row[1]
    return -1


def extractData(fileName, id):
    file = open(fileName)
    csvreader = csv.reader(file)
    data = []
    header = []
    header = next(csvreader)
    columnNo = header.index("SIS User ID")
    data.append(header)
    # header = next(csvreader)
    # data.append(header)
    for row in csvreader:

        if row[columnNo].isnumeric() and int(row[columnNo])==id:
            data.append(row)
            break
    return data


# ============================================
# Web Views / Routes
# ============================================

# LTI Launch
@app.route('/launch', methods=['POST', 'GET'])
@lti(error=error, request='initial', role='any', app=app)
def launch(lti=lti):
    """
    Returns the launch page
    request.form will contain all the lti params
    """

    # example of getting lti data from the request
    # let's just store it in our session
    session['lis_person_name_full'] = request.form.get('lis_person_name_full')
    session['lis_person_sourcedid'] = request.form.get('lis_person_sourcedid')
    session['context_id'] = request.form.get('context_id')
    session['user_id'] = request.form.get('user_id')
    session["roles"] = request.form.get('roles')
    session["context_label"] = request.form.get('context_label')
    session["custom_canvas_assignment_title"] = request.form.get('custom_canvas_assignment_title')
    # return '~/' + str(session['context_label'])
    basePath = "/home/Fizzaa39/"
    dirPath = basePath + str(session['context_label'])
    csvpath = dirPath + '/mapping.csv'
    if not os.path.isdir(dirPath):
        os.makedirs(dirPath)
        f =  open(csvpath, 'w')
        writer = csv.writer(f)
        writer.writerow(['Assignment','File Name'])
        f.close()
    # Write the lti params to the console
    app.logger.info(json.dumps(request.form, indent=2))
    data  = []
    if os.path.isfile(csvpath):
        file = open(csvpath)
        csvreader = csv.reader(file)
        header = []
        header = next(csvreader)
        for row in csvreader:
            url = ("https://fizzaa39.pythonanywhere.com/download/"+session["context_label"]+'/'+row[1].strip()).replace(" ", "-")
            url2 = ("https://fizzaa39.pythonanywhere.com/delete/"+session["context_label"]+ '/'+ row[0].strip() + '/' + row[1].strip()).replace(" ", "-")
            data.append([row[0], row[1], url, url2])
    else:
        return return_error("Mapping file not found")
    # return "Here"
    if session["roles"]=="Learner":
        assignTitle = session["custom_canvas_assignment_title"].replace(" ", "-")
        course = session["context_label"].replace(" ", "-")
        return render_template('studenthome.html', data=data,custom_canvas_assignment_title=assignTitle, lis_person_name_full=session['lis_person_name_full'], user_id =session['user_id'] , sourcedid =session["lis_person_sourcedid"], course = course , roles=session['roles'])
    else:
        return render_template('launch.html', data=data, custom_canvas_assignment_title=session["custom_canvas_assignment_title"], lis_person_name_full=session['lis_person_name_full'], user_id =session['user_id'] , sourcedid =session["lis_person_sourcedid"], roles=session['roles'], course = session["context_label"] )


@app.route('/student/<path:sourcedid>/<path:course>/<path:assignName>', methods=['GET', 'POST'])
def getFeedback (sourcedid, assignName, course):
    course = course.replace("-", " ")
    assignName = assignName.replace("-", " ")
    fileName = getCSVFilename(assignName, course)
    data = extractData("/home/Fizzaa39/" + course + "/" + fileName, int(sourcedid))
    return render_template('student.html', data=data, datalen=len(data[0]), assignName=assignName)



@app.route('/uploader/<path:course>', methods = ['GET', 'POST'])
def upload_file(course):

    if request.method == 'POST':
        f = request.files['file']
        basePath = "/home/Fizzaa39/"
        dirPath = basePath + course + '/' + f.filename
        f.save(dirPath)
        if os.path.isfile(basePath+ course + '/mapping.csv'):
            path = "/home/Fizzaa39/" + course + '/'
            filename = path + 'mapping.csv'
            tempfile = NamedTemporaryFile(mode='w', delete=False)
            fields = ['Assignment', 'File Name']
            found  = False
            with open(filename, 'r') as csvfile, tempfile:
                reader = csv.DictReader(csvfile, fieldnames=fields)
                writer = csv.DictWriter(tempfile, fieldnames=fields)
                for row in reader:
                    if row['Assignment'] == request.form['aname']:
                        found=True
                        row['Assignment'], row['File Name'] = row['Assignment'], f.filename
                    row = {'Assignment': row['Assignment'], 'File Name': row['File Name']}
                    writer.writerow(row)
            shutil.move(tempfile.name, filename)
            if found==False:
                with open(filename, 'a', newline='') as f_object:
                    writer_object = csv.writer(f_object)
                    writer_object.writerow([request.form['aname'], f.filename])
                    f_object.close()
            return "File is saved, please refresh the page."
        else:
            return return_error("Mapping file not found")




# Home page
@app.route('/', methods=['GET'])
def index(lti=lti):
    return render_template('index.html')

# Home page
@app.route('/instructor/', methods=['GET'])
def instructorView():
    if os.path.isfile('/home/Fizzaa39/feedback.txt'):
        data = []
        file1 = open('/home/Fizzaa39/feedback.txt', 'r')
        count = 0
        while True:
            count += 1
            line = file1.readline()
            if not line:
                break
            line = line.strip()
            lst = line.split()
            url = str("https://fizzaa39.pythonanywhere.com/download/"+lst[1].strip()).replace(" ", "-")
            return url
            data.append([lst[0].strip(), lst[1].strip(), url])
        return render_template('instructiorView.html', data = data)
    else:
        return return_error('''There is no such file as feedback.txt. Kindly add it from the main launch page.''')

@app.route('/download/<path:course>/<path:filename>', methods=['GET', 'POST'])
def downloadFile (filename, course):
    #For windows you need to use drive name [ex: F:/Example.pdf]
    filename = filename.replace("-", " ")
    course = course.replace("-", " ")
    path = "/home/Fizzaa39/" + course +'/'+filename
    return send_file(path, as_attachment=True)

@app.route('/delete/<path:course>/<path:assignname>/<path:filename>', methods=['GET', 'POST'])
def deleteFile (course, assignname, filename):
    #For windows you need to use drive name [ex: F:/Example.pdf]
    filename = filename.replace("-", " ")
    assignname = assignname.replace("-", " ")
    course = course.replace("-", " ")
    path = "/home/Fizzaa39/" + course +'/'+filename
    feedbackpath = "/home/Fizzaa39/" + course +'/mapping.csv'
    if os.path.exists(path):
        # os.remove(path)
        df = pd.read_csv(feedbackpath)
        # return str(list(df.columns))
        df =  df[df["Assignment"] != assignname]
        df.to_csv(feedbackpath, index=False)
        return "The feedback for this Assignment has been deleted."
    else:
        return "The file does not exist on server"


# LTI XML Configuration
@app.route("/xml/", methods=['GET'])
def xml():
    """
    Returns the lti.xml file for the app.
    XML can be built at https://www.eduappcenter.com/
    """
    try:
        return Response(render_template(
            'lti.xml'), mimetype='application/xml'
        )
    except:
        app.logger.error("Error with XML.")
        return return_error('''Error with XML. Please refresh and try again. If this error persists,
            please contact support. ''')