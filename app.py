from flask_mysqldb import MySQL
from flask import Flask, render_template, request, redirect, url_for, flash
import os
import speech_recognition as sr
import librosa
import numpy as np




app = Flask(__name__)



# MySQL configurations
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'voiceapp'        # or your MySQL user
app.config['MYSQL_PASSWORD'] = 'root123888'  # your root password
app.config['MYSQL_DB'] = 'voice_app_production'

mysql = MySQL(app)

@app.route('/test_db')
def test_db():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users")
    result = cur.fetchall()
    cur.close()
    return f"Users in DB: {result}"






# ---------- CONFIG ----------

app.secret_key = "secret_key_here"



# Ensure folders exist
if not os.path.exists("voices"):
    os.makedirs("voices")
if not os.path.exists("features"):
    os.makedirs("features")


# ---------- HELPER FUNCTIONS ----------
def record_voice(filename):
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎙 Speak now...")
        audio = r.listen(source)
        with open(filename, "wb") as f:
            f.write(audio.get_wav_data())
    print(f"✅ Voice recorded: {filename}")


def extract_features(file):
    # Load the audio file
    y, sr = librosa.load(file, sr=None)

    # Extract base MFCC features (13 coefficients)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)

    # Compute the first derivative (delta)
    delta = librosa.feature.delta(mfcc)

    # Compute the second derivative (delta-delta)
    delta2 = librosa.feature.delta(mfcc, order=2)

    # Combine all features vertically
    combined = np.vstack([mfcc, delta, delta2])

    # Take mean across time (to get one feature vector per file)
    mean_features = np.mean(combined, axis=1)

    return mean_features


# ---------- ROUTES ----------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip().lower()
        email = request.form["email"].strip()

        cursor = mysql.connection.cursor()
        
        # 1. Prepare/Record the voice and extract features
        voice_file = os.path.abspath(f"voices/{name}_voice{int(np.random.randint(100000))}.wav")
        feature_file = os.path.abspath(f"features/{name}_features{int(np.random.randint(100000))}.npy")

        record_voice(voice_file)
        features = extract_features(voice_file)
        np.save(feature_file, features)

        # 2. Check if user already exists (only need to SELECT the name)
        cursor.execute("SELECT name FROM users WHERE name=%s", (name,))
        user_exists = cursor.fetchone()

        # 3. Insert or check the main users table
        if user_exists:
            flash(f"✅ New voice recorded. Updating profile for {name}.", "info")
        else:
            # New user: Insert into the main users table
            try:
                # NOTE: The threshold_value is gone, so the query is shorter
                cursor.execute(
                    "INSERT INTO users (name, email) VALUES (%s, %s)",
                    (name, email)
                )
                mysql.connection.commit()
                flash(f"👤 User '{name}' registered successfully!", "success")
            except Exception as e:
                flash(f"Error registering user: {e}", "danger")
                cursor.close()
                return redirect(url_for("index"))
        
        # 4. Insert the new voice files into the voiceprints table (This remains)
        cursor.execute(
            "INSERT INTO voiceprints (user_name, voice_file, feature_file) VALUES (%s, %s, %s)",
            (name, voice_file, feature_file)
        )
        mysql.connection.commit()
        
        flash(f"Successfully added new voice sample for {name}.", "success")

        cursor.close()
        return redirect(url_for("index"))

    return render_template("register.html")



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form["name"].strip().lower()
        cursor = mysql.connection.cursor()

        # --- SET FIXED THRESHOLD HERE ---
        FIXED_THRESHOLD = 50.0 
        
        # 1. Check if user exists (simple check)
        cursor.execute("SELECT name FROM users WHERE name=%s", (name,))
        user_exists = cursor.fetchone()
        
        if not user_exists:
            flash("User not found! Please register first.", "danger")
            cursor.close()
            return redirect(url_for("login"))

        # 2. Fetch ALL registered feature file paths (from the voiceprints table)
        cursor.execute("SELECT feature_file FROM voiceprints WHERE user_name=%s", (name,))
        feature_results = cursor.fetchall()
        
        if not feature_results:
            flash("No voiceprints found for this user. Please register first.", "danger")
            cursor.close()
            return redirect(url_for("login"))

        feature_files = [row[0] for row in feature_results] 

        # 3. Record new voice for login and extract features
        login_file = f"voices/{name}_login.wav"
        record_voice(login_file)
        login_features = extract_features(login_file)

        access_granted = False
        best_similarity_score = float('inf') 

        # 4. Compare with each stored feature file
        for feature_file in feature_files:
            try:
                reg_features = np.load(feature_file)
                similarity = np.linalg.norm(reg_features - login_features)
                
                if similarity < best_similarity_score:
                    best_similarity_score = similarity

                # Use the FIXED THRESHOLD for match check
                if similarity < FIXED_THRESHOLD:
                    access_granted = True
                    break
            except Exception as e:
                print(f"⚠ Error loading {feature_file}: {e}")

        # 5. Decision and message
        if access_granted:
            flash(f"✅ Access Granted! Welcome {name.capitalize()}! Score: {best_similarity_score:.2f} (Threshold: {FIXED_THRESHOLD:.2f})", "success")
        else:
            sim_text = f"{best_similarity_score:.2f}" if best_similarity_score != float('inf') else "N/A"
            flash(f"❌ Access Denied! No matching voice. Score: {sim_text} (Threshold: {FIXED_THRESHOLD:.2f})", "danger")

        cursor.close()
        return redirect(url_for("login")) 

    return render_template("login.html")




if __name__ == "__main__":
    app.run(debug=True)