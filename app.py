from flask import Flask, render_template, request, redirect, url_for, session
import qrcode
import cv2
import pandas as pd
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "secret123"

ATTENDANCE_FILE = "attendance.csv"
STUDENTS_FILE = "students.csv"

# Ensure attendance file exists
if not os.path.exists(ATTENDANCE_FILE) or os.stat(ATTENDANCE_FILE).st_size == 0:
    df = pd.DataFrame(columns=["StudentID", "Name", "Date", "Time"])
    df.to_csv(ATTENDANCE_FILE, index=False)


# 🔐 LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == "teacher" and password == "123":
            session['role'] = 'admin'
            return redirect('/admin')

        elif username == "student" and password == "123":
            session['role'] = 'student'
            return redirect('/student')

        else:
            return "Invalid Login"

    return render_template('login.html')


# HOME
@app.route('/')
def home():
    return redirect('/login')


# 👨‍🏫 ADMIN DASHBOARD
@app.route('/admin')
def admin():
    if session.get('role') != 'admin':
        return redirect('/login')
    return render_template('admin_dashboard.html')


# 👨‍🎓 STUDENT DASHBOARD
@app.route('/student')
def student():
    if session.get('role') != 'student':
        return redirect('/login')
    return render_template('scan.html')


# 📦 MANAGE STUDENTS
@app.route('/manage_students', methods=['GET', 'POST'])
def manage_students():
    if session.get('role') != 'admin':
        return redirect('/login')

    if os.path.exists(STUDENTS_FILE):
        df = pd.read_csv(STUDENTS_FILE)
    else:
        df = pd.DataFrame(columns=["RollNo", "Name"])

    if request.method == 'POST':
        roll = str(request.form['roll'])
        name = request.form['name']

        df.loc[len(df)] = [roll, name]
        df.to_csv(STUDENTS_FILE, index=False)

    data = df.to_dict(orient='records')
    return render_template('manage_students.html', data=data)


# 🔳 GENERATE QR
@app.route('/generate', methods=['GET', 'POST'])
def generate():
    if session.get('role') != 'admin':
        return redirect('/login')

    students = pd.read_csv(STUDENTS_FILE)
    students['RollNo'] = students['RollNo'].astype(str)

    qr_path = None
    name = None

    if request.method == 'POST':
        roll = str(request.form['roll'])

        student = students[students['RollNo'] == roll]

        if not student.empty:
            name = student.iloc[0]['Name']
            data = f"{roll},{name}"

            filename = f"{roll}.png"
            filepath = os.path.join("static", filename)

            qr = qrcode.make(data)
            qr.save(filepath)

            qr_path = filename

    return render_template(
        'generate.html',
        qr_code=qr_path,
        name=name,
        students=students.to_dict(orient='records')
    )


# 📷 SCAN QR
@app.route('/scan')
def scan():
    if session.get('role') not in ['admin', 'student']:
        return redirect('/login')

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # 🔥 better for Windows
    detector = cv2.QRCodeDetector()
    message = None

    if not cap.isOpened():
        return render_template('scan.html', message="❌ Camera not accessible")

    while True:
        success, img = cap.read()
        if not success:
            message = "❌ Failed to access camera"
            break

        # Show camera FIRST (important)
        cv2.imshow('QR Scanner', img)

        data, bbox, _ = detector.detectAndDecode(img)

        if data:
            try:
                student_id, name = data.split(',')
            except:
                message = "❌ Invalid QR format"
                break

            students = pd.read_csv(STUDENTS_FILE)
            students['RollNo'] = students['RollNo'].astype(str)

            # 🔒 Fake QR check
            if not ((students['RollNo'] == str(student_id)).any()):
                message = "❌ Fake QR detected!"
                break

            now = datetime.now()

            try:
                df = pd.read_csv(ATTENDANCE_FILE)
                df['StudentID'] = df['StudentID'].astype(str)
            except:
                df = pd.DataFrame(columns=["StudentID", "Name", "Date", "Time"])

            # ✅ Prevent duplicate
            if not ((df['StudentID'] == str(student_id)) &
                    (df['Date'] == now.strftime("%Y-%m-%d"))).any():

                df.loc[len(df)] = [
                    student_id,
                    name,
                    now.strftime("%Y-%m-%d"),
                    now.strftime("%H:%M:%S")
                ]

                df.to_csv(ATTENDANCE_FILE, index=False)
                message = f"✅ Attendance marked for {name}"
            else:
                message = "⚠️ Already marked today"

            # Show success for 2 sec
            cv2.putText(img, message, (30, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
            cv2.imshow('QR Scanner', img)
            cv2.waitKey(2000)

            break

        # ESC to exit manually
        if cv2.waitKey(1) == 27:
            message = "Scanner closed"
            break

    cap.release()
    cv2.destroyAllWindows()

    return render_template('scan.html', message=message)


# 📊 ATTENDANCE (Present / Absent)
@app.route('/attendance')
def attendance():
    if session.get('role') != 'admin':
        return redirect('/login')

    # Load students
    students = pd.read_csv(STUDENTS_FILE)
    students['RollNo'] = students['RollNo'].astype(str)

    # Load attendance
    try:
        attendance = pd.read_csv(ATTENDANCE_FILE)
        attendance['StudentID'] = attendance['StudentID'].astype(str)
    except:
        attendance = pd.DataFrame(columns=["StudentID", "Name", "Date", "Time"])

    # Merge
    merged = pd.merge(
        students,
        attendance,
        how='left',
        left_on='RollNo',
        right_on='StudentID'
    )

    # ✅ FIX: Use correct Name column
    merged['Name'] = merged['Name_x']

    # ✅ Status
    merged['Status'] = merged['StudentID'].apply(
        lambda x: "Present" if pd.notna(x) else "Absent"
    )

    # ✅ Keep only required columns
    merged = merged[['RollNo', 'Name', 'Status']]

    # Sort
    merged = merged.sort_values(by='RollNo')

    data = merged.to_dict(orient='records')
    return render_template('attendance.html', data=data)


# 🚀 RUN
if __name__ == '__main__':
    app.run(debug=True)