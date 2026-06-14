PIGSP - Platforma Inteligentă de Gestionare a Stagiilor de Practică

O aplicație web dezvoltată pentru digitalizarea, eficientizarea și automatizarea procesului de desfășurare a stagiilor de practică universitare. Platforma conectează studenții cu angajatorii, integrând un modul de inteligență artificială pentru orientare în carieră și potrivire cu ofertele, alături de un sistem de generare și securizare digitală a documentelor oficiale.

Tehnologii Utilizate
Backend: Python, Framework-ul Django
Bază de date: PostgreSQL
Inteligență Artificială: Google Gemini API (google-genai)
Generare PDF: xhtml2pdf, reportlab
Frontend: HTML5, CSS3, Bootstrap 5, JavaScript

Pentru a rula acest proiect local, asigură-te că ai instalate următoarele:
Python 3.10 sau o versiune mai recentă
PostgreSQL instalat și rulând pe mașina locală

Instalare și configurare
1. Clonarea proiectului și inițializarea mediului virtual
Deschide un terminal și rulează următoarele comenzi:
```bash
git clone 
cd internship_platform
python -m venv .venv
```
2. Activarea mediului virtual

Pe Windows:
```bash
.venv\Scripts\activate
```
Pe Linux / macOS:
```bash
source .venv/bin/activate
```
3. Instalarea dependențelor
Instalează toate pachetele necesare rulând:

```bash
pip install -r requirements.txt
```
4. Configurarea bazei de date și a variabilelor de mediu
Creează o bază de date PostgreSQL goală (ex: internship_db) folosind pgAdmin sau linia de comandă.

Apoi, în folderul principal al proiectului, fă o copie a fișierului .env.template și redenumește-o în .env. Completează fișierul cu datele tale de conectare:

```env
Configurări bază de date
DB_NAME=internship_db
DB_USER=utilizatorul_tau_postgres
DB_PASSWORD=parola_ta_postgres
DB_HOST=localhost
DB_PORT=5432

Configurare API AI
GEMINI_API_KEY=cheia_ta_de_la_google_ai_studio

Configurare email (notificări)
EMAIL_HOST_USER=adresa_ta_de_email@gmail.com
EMAIL_HOST_PASSWORD=parola_de_aplicatie
```
5. Aplicarea migrărilor
Pentru a crea structura tabelelor în baza de date, folosește:

```bash
python manage.py makemigrations
python manage.py migrate
```
6. Rularea serverului local
Pornește serverul Django:
```bash
python manage.py runserver
```
Aplicația va fi acum disponibilă în browser la adresa: http://127.0.0.1:8000/
