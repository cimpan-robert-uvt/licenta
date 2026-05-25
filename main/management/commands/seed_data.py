from datetime import date, timedelta
import random

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import (
    User,
    StudentProfile,
    CompanyProfile,
    StudentCV,
    CVEducation,
    CVExperience,
    CVSkill,
)
from main.models import InternshipOffer

PASSWORD = "Robi1234!!!"

COMPANY_DOMAIN_DATA = [
    {
        "domain": "informatica",
        "company_name": "Solutii TehNova",
        "industry": "Software",
        "website": "https://technova.example.com",
        "address": "Bucuresti",
        "contact_person": "Robert Cimpan",
        "contact_phone": "0711000001",
    },
    {
        "domain": "mecanica",
        "company_name": "Sisteme AutoDrive",
        "industry": "Auto",
        "website": "https://autodrive.example.com",
        "address": "Cluj-Napoca",
        "contact_person": "Robert Cimpan",
        "contact_phone": "0711000002",
    },
    {
        "domain": "marketing",
        "company_name": "Agentia MarketLift",
        "industry": "Marketing",
        "website": "https://marketlift.example.com",
        "address": "Timisoara",
        "contact_person": "Robert Cimpan",
        "contact_phone": "0711000003",
    },
    {
        "domain": "finante",
        "company_name": "FinAxis Capital",
        "industry": "Finante",
        "website": "https://finaxis.example.com",
        "address": "Iasi",
        "contact_person": "Robert Cimpan",
        "contact_phone": "0711000004",
    },
    {
        "domain": "arte",
        "company_name": "Studio DesignForge",
        "industry": "Design",
        "website": "https://designforge.example.com",
        "address": "Brasov",
        "contact_person": "Robert Cimpan",
        "contact_phone": "0711000005",
    },
]

OFFER_TEMPLATES = {
    "informatica": [
        {
            "title": "Software Engineer Intern (Python / Django)",
            "description": "Suntem în căutarea unui student pasionat de dezvoltare web pentru a se alătura echipei noastre de Backend.\n\nÎn cadrul acestui stagiu de practică, vei lucra direct pe produsul nostru principal, optimizând fluxurile de date și implementând funcționalități noi. Vei avea parte de mentorat 1-la-1, sesiuni de pair-programming și te vei familiariza cu bunele practici din industrie.\n\nResponsabilități:\n• Dezvoltarea și mentenanța de API-uri folosind Django REST Framework.\n• Scrierea de teste unitare pentru asigurarea calității codului.\n• Colaborarea cu echipa de Frontend.",
            "requirements": "Cerințe și profil ideal:\n• Cunoștințe solide de Python și OOP.\n• Familiaritate cu un framework web (Django sau Flask reprezintă un avantaj).\n• Înțelegerea bazelor de date relaționale (SQL).\n• Cunoștințe de bază de Git (version control).\n• Dorința de a rezolva probleme complexe.",
        },
        {
            "title": "Cloud & DevOps Engineering Internship",
            "description": "Vrei să afli cum funcționează aplicațiile cu milioane de utilizatori? Echipa noastră de infrastructură caută un stagiar dornic să învețe despre Cloud și automatizare.\n\nVei fi integrat într-un mediu Agile și vei contribui la procesele noastre de integrare și livrare continuă (CI/CD).\n\nResponsabilități:\n• Suport în configurarea și monitorizarea infrastructurii pe AWS.\n• Containerizarea aplicațiilor folosind Docker.\n• Automatizarea task-urilor repetitive folosind scripturi de Bash sau Python.",
            "requirements": "Cerințe și profil ideal:\n• Cunoștințe de bază despre sisteme de operare (Linux/Unix).\n• Înțelegerea conceptelor de rețelistică și Cloud Computing.\n• Cunoștințe de bază într-un limbaj de scripting.\n• Atenție la detalii și un mindset orientat spre securitate.",
        },
        {
            "title": "Junior Frontend Developer (React)",
            "description": "Alătură-te echipei noastre de produs pentru a construi interfețe web moderne, rapide și accesibile.\n\nCa stagiar Frontend, vei contribui direct la experiența vizuală a utilizatorilor noștri, învățând de la ingineri seniori cum se construiesc aplicații Single Page Application (SPA).\n\nResponsabilități:\n• Implementarea de ecrane noi și componente UI reutilizabile în React.\n• Optimizarea aplicației pentru performanță și responsive design.\n• Rezolvarea de bug-uri de interfață.",
            "requirements": "Cerințe și profil ideal:\n• Baze solide de HTML5, CSS3 și JavaScript (ES6+).\n• Familiaritate cu o bibliotecă modernă (React.js, Vue sau Angular).\n• Înțelegerea modului în care funcționează asincronismul în JS.\n• Portofoliul cu proiecte personale reprezintă un plus.",
        },
        {
            "title": "QA Automation Engineering Intern",
            "description": "Calitatea este pe primul loc pentru noi. Căutăm un intern pasionat de testare care să ne ajute să construim o rețea de siguranță invizibilă pentru codul nostru.\n\nVei învăța să gândești critic și să identifici vulnerabilitățile înainte ca acestea să ajungă la clienți.\n\nResponsabilități:\n• Crearea și mentenanța scripturilor de testare automată (Selenium, Cypress).\n• Raportarea și documentarea bug-urilor descoperite.\n• Colaborarea strânsă cu dezvoltatorii pentru reproducerea problemelor.",
            "requirements": "Cerințe și profil ideal:\n• Gândire analitică și atenție extremă la detalii.\n• Cunoștințe de bază de programare (Python, Java sau JS).\n• Înțelegerea conceptelor de bază din testarea software (Black-box, White-box).\n• Atitudine proactivă.",
        },
        {
            "title": "Data Analytics & BI Intern",
            "description": "Dacă iubești cifrele și vrei să transformi datele brute în decizii de business, acesta este locul potrivit. Vei lucra cu volume mari de date pentru a identifica trenduri și anomalii.\n\nResponsabilități:\n• Curățarea și pregătirea seturilor de date pentru analiză.\n• Construirea de dashboard-uri vizuale interactive (Tableau / Power BI).\n• Generarea de rapoarte saptămânale pentru departamentul de management.",
            "requirements": "Cerințe și profil ideal:\n• Cunoștințe avansate de SQL pentru interogarea bazelor de date.\n• Familiaritate cu Excel avansat (Pivot tables, VLOOKUP).\n• Cunoștințe de analiză în Python (Pandas, NumPy) reprezintă un avantaj.\n• Capacitatea de a comunica vizual informații complexe.",
        },
    ],
    "mecanica": [
        {
            "title": "Inginer Proiectare CAD (Internship)",
            "description": "Alătură-te echipei noastre de cercetare și dezvoltare pentru a contribui la designul viitoarelor componente auto.\n\nVei lucra alături de ingineri cu experiență în modelarea 3D a pieselor complexe și vei învăța fluxul complet de la concept la manufacturare.\n\nResponsabilități:\n• Realizarea și modificarea modelelor 3D folosind CATIA sau SolidWorks.\n• Generarea desenelor de execuție la standarde industriale.\n• Participarea la ședințele de revizuire a designului (Design Reviews).",
            "requirements": "Cerințe și profil ideal:\n• Student în an terminal la Inginerie Mecanică / Autovehicule Rutiere.\n• Baze solide de desen tehnic și geometrie descriptivă.\n• Experiență de bază cu un software CAD (SolidWorks, CATIA, AutoCAD).\n• Capacitate bună de vizualizare spațială.",
        },
        {
            "title": "Stagiu Inginerie de Producție & Proces",
            "description": "Descoperă cum se fabrică produsele la scară industrială! Căutăm un intern interesat de optimizarea proceselor de fabricație.\n\nResponsabilități:\n• Analiza fluxurilor tehnologice direct pe linia de producție.\n• Identificarea 'bottleneck-urilor' și propunerea de soluții de eficientizare.\n• Actualizarea documentației și a instrucțiunilor de lucru pentru operatori.",
            "requirements": "Cerințe și profil ideal:\n• Cunoștințe de bază despre tehnologia materialelor și procese de prelucrare.\n• Familiaritate cu conceptele de Lean Manufacturing (5S, Kaizen).\n• Abilități foarte bune de comunicare și lucru pe teren.\n• Orientare către rezolvarea practică a problemelor.",
        },
        {
            "title": "Testare Sisteme de Propulsie - Stagiu Practică",
            "description": "Vrei să faci parte din tranziția către vehiculele viitorului? Departamentul nostru de testare motoare și sisteme hibride își mărește echipa.\n\nResponsabilități:\n• Asistarea inginerilor la montarea prototipurilor pe standurile de testare.\n• Colectarea și centralizarea datelor termodinamice și de vibrații.\n• Suport în redactarea rapoartelor de calibrare.",
            "requirements": "Cerințe și profil ideal:\n• Cunoștințe solide de termodinamică și mecanica fluidelor.\n• Pasiune pentru industria auto și noile tehnologii de propulsie.\n• Cunoștințe de bază în utilizarea instrumentelor de măsură (șubler, micrometru, senzori).",
        },
        {
            "title": "Internship Asigurarea Calității (QA Industrial)",
            "description": "Calitatea pieselor mecanice este vitală pentru siguranța clienților noștri. Ca intern în departamentul de Calitate, vei învăța aplicarea standardelor ISO în producție.\n\nResponsabilități:\n• Efectuarea de măsurători dimensionale pe eșantioane de piese.\n• Participarea la auditurile interne de calitate.\n• Analiza defectelor și suport în implementarea diagramelor Ishikawa / 8D.",
            "requirements": "Cerințe și profil ideal:\n• Înțelegerea toleranțelor și a ajustajelor mecanice.\n• Rigurozitate, etică și atenție deosebită la detalii.\n• Cunoștințe de utilizare MS Office (în special Excel pentru trasabilitate).",
        },
        {
            "title": "Stagiar Mentenanță Echipamente Industriale",
            "description": "Fără o mentenanță corectă, fabrica se oprește. Căutăm un student proactiv pentru a sprijini planificarea mentenanței preventive a roboților și liniilor de asamblare.\n\nResponsabilități:\n• Actualizarea bazei de date cu istoricul intervențiilor tehnice.\n• Verificarea stocurilor de piese de schimb critice.\n• Asistarea tehnicienilor seniori în diagnosticarea defecțiunilor pneumatice și hidraulice.",
            "requirements": "Cerințe și profil ideal:\n• Cunoștințe teoretice de organe de mașini, cinematică și hidraulică.\n• Capacitatea de a citi și interpreta scheme tehnice (mecanice și electrice de bază).\n• Dorința de a lucra într-un mediu dinamic de hală industrială.",
        },
    ],
    "marketing": [
        {
            "title": "Stagiar Marketing Digital & PPC",
            "description": "Pasionat de performanță și conversii? Alătură-te echipei noastre pentru a învăța cum se gestionează bugete reale pe platformele de advertising.\n\nResponsabilități:\n• Setarea și monitorizarea campaniilor pe Google Ads și Meta Ads.\n• Analiza cuvintelor cheie (Keyword Research) pentru campaniile de Search.\n• Generarea de rapoarte de performanță (CTR, CPC, ROI) folosind Google Analytics.",
            "requirements": "Cerințe și profil ideal:\n• Interes puternic pentru marketingul bazat pe date (Data-driven marketing).\n• Familiaritate cu conceptele de bază PPC și SEO.\n• Excel bunicel pentru analiza datelor.\n• Certificările Google Skillshop reprezintă un plus major.",
        },
        {
            "title": "Content Creation & Social Media Intern",
            "description": "Ești vocea creativă a companiei noastre! Căutăm o persoană plină de idei care să ne ajute să creștem comunitatea online.\n\nResponsabilități:\n• Crearea de calendare editoriale pentru Instagram, LinkedIn și TikTok.\n• Redactarea de texte captivante (copywriting) pentru postări și articole de blog.\n• Urmărirea tendințelor online și propunerea de formate noi virale.",
            "requirements": "Cerințe și profil ideal:\n• Abilități excelente de scriere și gramatică impecabilă.\n• Experiență în folosirea rețelelor sociale din perspectivă de business.\n• Noțiuni elementare de design (ex: utilizarea Canva) sau editare video scurtă (CapCut).",
        },
        {
            "title": "Internship SEO & Optimizare Web",
            "description": "Descoperă secretele prin care site-urile ajung pe prima pagină în Google. Vei lucra alături de specialiștii noștri SEO pe proiecte de amploare.\n\nResponsabilități:\n• Realizarea de audituri tehnice de bază pentru site-urile partenerilor.\n• Optimizarea meta-descrierilor, tag-urilor și a structurii URL-urilor (On-page SEO).\n• Identificarea oportunităților de link-building (Off-page SEO).",
            "requirements": "Cerințe și profil ideal:\n• Înțelegerea modului în care funcționează motoarele de căutare.\n• Baze de HTML și structura paginilor web.\n• Răbdare, perseverență și gândire analitică.",
        },
        {
            "title": "Asistent PR și Comunicare Corporativă",
            "description": "Imaginea companiei noastre este în mâinile tale. Acest rol îți va oferi ocazia să înveți cum se comunică eficient cu mass-media și stakeholderii.\n\nResponsabilități:\n• Redactarea de comunicate de presă și mape de prezentare.\n• Monitorizarea aparițiilor media și crearea revistei presei zilnice.\n• Asistarea în organizarea evenimentelor de lansare sau a webinariilor.",
            "requirements": "Cerințe și profil ideal:\n• Student la Comunicare, Jurnalism sau Relații Publice.\n• Abilități excepționale de comunicare verbală și scrisă.\n• Capacitatea de a adapta mesajul în funcție de audiență.\n• Profesionalism și diplomație.",
        },
        {
            "title": "Marketing Research Intern",
            "description": "Înainte de a lansa un produs, trebuie să ne înțelegem piața. Ca stagiar de research, vei fi 'detectivul' nostru pentru insight-uri de consumator.\n\nResponsabilități:\n• Analiza comportamentului concurenței (benchmarking).\n• Crearea de chestionare de satisfacție și focus grupuri.\n• Sintetizarea feedback-ului în prezentări pentru echipa de management.",
            "requirements": "Cerințe și profil ideal:\n• Gândire critică și obiectivitate.\n• Cunoștințe de statistică de bază.\n• Familiaritate cu instrumente de sondaj (SurveyMonkey, Typeform).\n• Abilitatea de a structura logic o prezentare PowerPoint.",
        },
    ],
    "finante": [
        {
            "title": "Stagiu Analist Financiar (FP&A)",
            "description": "Vrei să înțelegi cum se planifică viitorul financiar al unei corporații? Echipa de Planificare și Analiză Financiară caută un coleg nou.\n\nResponsabilități:\n• Suport în pregătirea bugetelor anuale și a forecast-urilor lunare.\n• Analiza deviațiilor dintre rezultatele reale și cele planificate (Variance Analysis).\n• Crearea și mentenanța modelelor financiare în Excel.",
            "requirements": "Cerințe și profil ideal:\n• Student la Finanțe, Contabilitate sau Cibernetică.\n• Excel la nivel avansat (funcții complexe, modelare, shortcut-uri).\n• Înțelegerea solidă a celor 3 situații financiare (P&L, Bilanț, Cash Flow).\n• Atenție absolută la detalii.",
        },
        {
            "title": "Internship Contabilitate și Raportare",
            "description": "Dacă iubești ordinea și procedurile clare, te așteptăm în departamentul de Contabilitate, inima financiară a companiei noastre.\n\nResponsabilități:\n• Verificarea și înregistrarea facturilor de la furnizori (Accounts Payable).\n• Reconcilierea extraselor de cont bancare.\n• Asistarea echipei în procesul de închidere de lună (Month-end close).",
            "requirements": "Cerințe și profil ideal:\n• Cunoștințe teoretice foarte bune de contabilitate românească (sau IFRS).\n• Dorință de învățare a unui sistem ERP (SAP, Oracle sau similar).\n• Corectitudine, integritate și un mod de lucru organizat.",
        },
        {
            "title": "Stagiu Audit Intern & Conformitate",
            "description": "Învață cum se evaluează și se protejează activele unei companii. Rolul de audit îți va oferi o perspectivă de ansamblu asupra tuturor departamentelor.\n\nResponsabilități:\n• Participarea la testarea eficienței controalelor interne din diverse proceduri.\n• Identificarea riscurilor operaționale și financiare.\n• Suport în documentarea și redactarea rapoartelor de audit intern.",
            "requirements": "Cerințe și profil ideal:\n• Curiozitate profesională, obiectivitate și scepticism sănătos.\n• Cunoștințe de evaluare a riscului.\n• Abilități bune de redactare a rapoartelor.\n• Confidențialitate absolută.",
        },
        {
            "title": "Asistent Trezorerie și Cash Management",
            "description": "Lichiditatea este 'sângele' oricărei companii. Vino să înveți cum se gestionează zilnic relația cu băncile și fluxul de numerar.\n\nResponsabilități:\n• Extragerea rapoartelor de încasări și plăți din platformele bancare.\n• Suport în prognoza necesarului de lichiditate (Cash flow forecast).\n• Asistarea în administrarea portofoliului de credite și garanții bancare.",
            "requirements": "Cerințe și profil ideal:\n• Înțelegerea conceptelor de risc valutar și rate ale dobânzii.\n• Bune abilități de comunicare pentru relaționarea cu instituțiile bancare.\n• Gândire rapidă și capacitate de analiză numerică.",
        },
        {
            "title": "Junior Investment Research Intern",
            "description": "Pasionat de piețele de capital și bursă? Oferim un stagiu în care vei analiza companii tranzacționate și industrii globale.\n\nResponsabilități:\n• Colectarea de date macroeconomice și sectoriale.\n• Analiza rapoartelor trimestriale ale companiilor listate.\n• Suport în redactarea sumarului investițional pentru managerii de portofoliu.",
            "requirements": "Cerințe și profil ideal:\n• Pasiune demonstrată pentru piața de capital (urmărești piețele, citești presa financiară).\n• Cunoștințe de evaluare a companiilor (multipli de piață, DCF de bază).\n• Engleză fluentă, necesară pentru parcurgerea documentației internaționale.",
        },
    ],
    "arte": [
        {
            "title": "UI/UX Design Intern",
            "description": "Ești pasionat de cum interacționează utilizatorii cu aplicațiile digitale? Căutăm un intern care să ne ajute să simplificăm fluxurile complexe de utilizare.\n\nVei lucra alături de Product Manageri și Developeri pentru a transforma ideile în prototipuri interactive.\n\nResponsabilități:\n• Crearea de wireframe-uri, user flows și prototipuri în Figma.\n• Participarea la interviuri cu utilizatorii și teste de uzabilitate.\n• Crearea și exportarea de asset-uri pentru echipa de dezvoltare.",
            "requirements": "Cerințe și profil ideal:\n• Cunoașterea principiilor de bază de design vizual (tipografie, culori, grid-uri).\n• Experiență de bază cu tool-uri de design (Figma, Adobe XD).\n• Portofoliul (chiar și cu concepte fictive) este absolut obligatoriu.",
        },
        {
            "title": "Internship Graphic Design & DTP",
            "description": "Vino să dai culoare brandurilor noastre! Căutăm un designer grafic junior care să creeze materiale vizuale cu impact, atât pentru mediul digital cât și pentru print.\n\nResponsabilități:\n• Realizarea de bannere, layout-uri pentru social media și infografice.\n• Pregătirea fișierelor pentru tipar (DTP - afișe, pliante, ambalaje).\n• Ajustarea și retușarea fotografiilor de produs.",
            "requirements": "Cerințe și profil ideal:\n• Stăpânire bună a Suitei Adobe (Illustrator, Photoshop, InDesign).\n• Ochi format pentru compoziție, proporții și estetică.\n• Capacitatea de a respecta un manual de identitate de brand (Brand Guidelines).",
        },
        {
            "title": "Junior Motion Designer",
            "description": "Imaginile statice nu sunt de ajuns? Dacă îți place să dai viață elementelor vizuale, rolul de Motion Design este perfect pentru tine.\n\nResponsabilități:\n• Crearea de animații scurte 2D (Lottie, SVG) pentru pagini web și aplicații.\n• Montaj video de bază și adăugarea de elemente grafice animate (lower thirds, tranzitii) pentru campaniile video.\n• Colaborarea cu echipa de marketing pentru crearea de story-uri dinamice.",
            "requirements": "Cerințe și profil ideal:\n• Experiență de lucru în After Effects și Premiere Pro.\n• Înțelegerea principiilor fundamentale ale animației.\n• Portofoliu video (showreel) cu animații sau editări personale.",
        },
        {
            "title": "Stagiu Ilustrație Comercială și Concept Art",
            "description": "Căutăm un artist digital talentat care să ajute la dezvoltarea universului vizual al jocurilor și publicațiilor noastre.\n\nResponsabilități:\n• Crearea de ilustrații originale pentru blog, editoriale și materiale promoționale.\n• Generarea de schițe și concepte (character design, environment) pentru proiecte noi.\n• Vectorizarea ilustrațiilor pentru a fi folosite la diverse scale.",
            "requirements": "Cerințe și profil ideal:\n• Stil de desen conturat, dar cu capacitatea de a se adapta la cerințele proiectului.\n• Experiență folosind tableta grafică și software specific (Procreate, Photoshop, Illustrator).\n• Un portofoliu puternic care să demonstreze versatilitate.",
        },
        {
            "title": "Brand Identity Design Intern",
            "description": "Un logo este doar începutul. Învață cum se construiește, se scalează și se protejează un brand complet de la zero.\n\nResponsabilități:\n• Asistarea Art Director-ului în definirea elementelor de identitate vizuală (logo, paletă de culori, tipografie).\n• Aplicarea identității vizuale pe diverse materiale (cărți de vizită, semnături email, template-uri de prezentare).\n• Documentarea și organizarea asset-urilor vizuale ale agenției.",
            "requirements": "Cerințe și profil ideal:\n• Pasiune profundă pentru tipografie și minimalism.\n• Abilitatea de a conceptualiza și de a explica raționamentul din spatele deciziilor de design.\n• Experiență cu Illustrator. Portofoliu obligatoriu cu cel puțin un proiect de branding.",
        },
    ],
}

LOCATIONS = ["Bucuresti", "Cluj-Napoca", "Timisoara", "Iasi", "Brasov"]

STUDENT_PROFILE_DATA = [
    {
        "domain": "informatica",
        "faculty": "Facultatea de Informatica",
        "specialization": "Informatica",
        "year_of_study": 2,
        "city": "Bucuresti",
    },
    {
        "domain": "mecanica",
        "faculty": "Facultatea de Mecanica",
        "specialization": "Inginerie mecanica",
        "year_of_study": 3,
        "city": "Cluj-Napoca",
    },
    {
        "domain": "marketing",
        "faculty": "Facultatea de Marketing",
        "specialization": "Marketing digital",
        "year_of_study": 2,
        "city": "Timisoara",
    },
    {
        "domain": "finante",
        "faculty": "Facultatea de Finante",
        "specialization": "Finante banci",
        "year_of_study": 3,
        "city": "Iasi",
    },
    {
        "domain": "arte",
        "faculty": "Facultatea de Arte",
        "specialization": "Design grafic",
        "year_of_study": 1,
        "city": "Brasov",
    },
]

STUDENT_SKILLS = {
    "informatica": [
        ("language", "Python"),
        ("program", "Git"),
        ("program", "SQL"),
    ],
    "mecanica": [
        ("program", "AutoCAD"),
        ("soft_skill", "Atentie la detalii"),
        ("program", "SolidWorks"),
    ],
    "marketing": [
        ("soft_skill", "Scriere continut"),
        ("program", "Google Analytics"),
        ("soft_skill", "Planificare campanii"),
    ],
    "finante": [
        ("program", "Excel"),
        ("soft_skill", "Gandire analitica"),
        ("program", "Power BI"),
    ],
    "arte": [
        ("program", "Figma"),
        ("program", "Adobe Photoshop"),
        ("soft_skill", "Creativitate"),
    ],
}


class Command(BaseCommand):
    help = "Populeaza baza de date cu utilizatori demo, profile, CV-uri si oferte."

    def add_arguments(self, parser):
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Rescrie ofertele si sectiunile de CV pentru utilizatorii seed.",
        )

    def handle(self, *args, **options):
        refresh = options.get("refresh", False)
        created_companies = 0
        created_company_profiles = 0
        created_offers = 0
        created_students = 0
        created_student_profiles = 0
        created_cvs = 0
        created_education = 0
        created_experience = 0
        created_skills = 0
        deleted_offers = 0
        deleted_education = 0
        deleted_experience = 0
        deleted_skills = 0

        with transaction.atomic():
            for i in range(5):
                username = "robert_hr" if i == 0 else f"robert_hr{i + 1}"
                email = f"cimpan.robert.tamas+hr{i + 1}@gmail.com"
                data = COMPANY_DOMAIN_DATA[i]

                user = User.objects.filter(username=username).first()
                if not user:
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=PASSWORD,
                        role="company",
                        first_name="Robert",
                        last_name=f"HR{i + 1}",
                    )
                    created_companies += 1
                else:
                    user.role = "company"
                    user.email = email
                    user.set_password(PASSWORD)
                    user.save(update_fields=["role", "email", "password"])

                company_profile, created = CompanyProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        "company_name": data["company_name"],
                        "domain": data["domain"],
                        "industry": data["industry"],
                        "website": data["website"],
                        "address": data["address"],
                        "contact_person": data["contact_person"],
                        "contact_phone": data["contact_phone"],
                    },
                )
                if created:
                    created_company_profiles += 1
                else:
                    CompanyProfile.objects.filter(pk=company_profile.pk).update(
                        company_name=data["company_name"],
                        full_company_name=data["full_company_name"],
                        domain=data["domain"],
                        industry=data["industry"],
                        website=data["website"],
                        address=data["address"],
                        contact_person=data["contact_person"],
                        contact_phone=data["contact_phone"],
                    )

                template_list = OFFER_TEMPLATES[data["domain"]]
                existing_offers = InternshipOffer.objects.filter(company=user)
                if refresh and existing_offers.exists():
                    deleted_offers += existing_offers.count()
                    existing_offers.delete()
                    offers_needed = 10
                else:
                    offers_needed = max(0, 10 - existing_offers.count())

                for idx in range(offers_needed):
                    offer_data = template_list[idx % len(template_list)]

                    title = offer_data["title"]
                    description = offer_data["description"]
                    requirements = offer_data["requirements"]

                    duration_weeks = random.randint(4, 12)
                    start_date = timezone.now().date() + timedelta(
                        days=random.randint(14, 120)
                    )
                    location = LOCATIONS[idx % len(LOCATIONS)]

                    InternshipOffer.objects.create(
                        company=user,
                        title=title,
                        description=description,
                        requirements=requirements,
                        location=location,
                        duration_weeks=duration_weeks,
                        start_date=start_date,
                        is_active=True,
                    )
                    created_offers += 1

            for i in range(5):
                username = "robert_student" if i == 0 else f"robert_student{i + 1}"
                email = f"cimpan.robert.tamas+s{i + 1}@gmail.com"
                data = STUDENT_PROFILE_DATA[i]

                user = User.objects.filter(username=username).first()
                if not user:
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=PASSWORD,
                        role="student",
                        first_name="Robert",
                        last_name=f"Student{i + 1}",
                    )
                    created_students += 1
                else:
                    user.role = "student"
                    user.email = email
                    user.set_password(PASSWORD)
                    user.save(update_fields=["role", "email", "password"])

                profile, created = StudentProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        "faculty": data["faculty"],
                        "domain": data["domain"],
                        "specialization": data["specialization"],
                        "year_of_study": data["year_of_study"],
                    },
                )
                if created:
                    created_student_profiles += 1
                else:
                    StudentProfile.objects.filter(pk=profile.pk).update(
                        faculty=data["faculty"],
                        domain=data["domain"],
                        specialization=data["specialization"],
                        year_of_study=data["year_of_study"],
                    )

                cv, created = StudentCV.objects.get_or_create(
                    user=user,
                    defaults={
                        "phone": f"071000000{i + 1}",
                        "email": email,
                        "linkedin": f"https://www.linkedin.com/in/robert-student{i + 1}/",
                        "city": data["city"],
                        "resume": (
                            "Student motivat, interesat sa invete si sa contribuie la proiecte reale. "
                            "Am experienta in proiecte academice si doresc un stagiu relevant."
                        ),
                    },
                )
                if created:
                    created_cvs += 1
                else:
                    StudentCV.objects.filter(pk=cv.pk).update(
                        phone=f"071000000{i + 1}",
                        email=email,
                        linkedin=f"https://www.linkedin.com/in/robert-student{i + 1}/",
                        city=data["city"],
                        resume=(
                            "Student motivat, interesat sa invete si sa contribuie la proiecte reale. "
                            "Am experienta in proiecte academice si doresc un stagiu relevant."
                        ),
                    )

                education_exists = CVEducation.objects.filter(cv=cv).exists()
                if refresh and education_exists:
                    deleted_education += CVEducation.objects.filter(cv=cv).count()
                    CVEducation.objects.filter(cv=cv).delete()
                    education_exists = False

                if not education_exists:
                    CVEducation.objects.create(
                        cv=cv,
                        school_name=data["faculty"],
                        start_date=date(timezone.now().year - 2, 10, 1),
                        end_date=date(timezone.now().year + 1, 7, 1),
                        details="Program de licenta cu proiecte practice si colaborari in echipa.",
                    )
                    created_education += 1

                experience_exists = CVExperience.objects.filter(cv=cv).exists()
                if refresh and experience_exists:
                    deleted_experience += CVExperience.objects.filter(cv=cv).count()
                    CVExperience.objects.filter(cv=cv).delete()
                    experience_exists = False

                if not experience_exists:
                    CVExperience.objects.create(
                        cv=cv,
                        institution_name="Stagiu de practica",
                        start_date=timezone.now().date() - timedelta(days=180),
                        end_date=timezone.now().date() - timedelta(days=30),
                        details="Contributii la proiecte interne, documentatie si testare.",
                    )
                    created_experience += 1

                existing_skills = CVSkill.objects.filter(cv=cv)
                if refresh and existing_skills.exists():
                    deleted_skills += existing_skills.count()
                    existing_skills.delete()
                    needed_skills = 3
                else:
                    needed_skills = max(0, 3 - existing_skills.count())

                if needed_skills:
                    for skill_type, skill_name in STUDENT_SKILLS[data["domain"]][
                        :needed_skills
                    ]:
                        CVSkill.objects.create(
                            cv=cv,
                            skill_type=skill_type,
                            skill_name=skill_name,
                        )
                        created_skills += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Seed finalizat. "
                f"Companii create: {created_companies}, Profile companii: {created_company_profiles}, "
                f"Oferte create: {created_offers}, Oferte sterse: {deleted_offers}. "
                f"Studenti creati: {created_students}, Profile studenti: {created_student_profiles}, "
                f"CV-uri create: {created_cvs}, Educatii create: {created_education}, "
                f"Experiente create: {created_experience}, Abilitati create: {created_skills}. "
                f"Educatii sterse: {deleted_education}, Experiente sterse: {deleted_experience}, "
                f"Abilitati sterse: {deleted_skills}."
            )
        )
