# -*- coding: utf-8 -*-
"""Compta Canard - application locale. Les donnees restent dans %LOCALAPPDATA%."""
import os, sqlite3, shutil, csv, sys, hashlib, re, json, urllib.request, subprocess, ssl, webbrowser
try:
    import certifi
except ImportError:
    certifi = None
from pathlib import Path
from datetime import date, datetime, timedelta
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = "Compta Canard"
VERSION = "2.2.0"
BASE = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ComptaCanard"
DB = BASE / "compta_canard.db"
DOCS = BASE / "documents"
BACKUPS = BASE / "backups"
BASE.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(exist_ok=True)
BACKUPS.mkdir(exist_ok=True)

def money(v):
    try: return f"{float(v):,.2f}".replace(",", " ").replace(".", ",")
    except (TypeError, ValueError): return "0,00"

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS entries(
          id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, party TEXT, number TEXT,
          date TEXT, due TEXT, category TEXT, ht REAL DEFAULT 0, rate REAL DEFAULT 20,
          vat REAL DEFAULT 0, ttc REAL DEFAULT 0, payment TEXT, status TEXT,
          notes TEXT, file TEXT, created TEXT);
        CREATE TABLE IF NOT EXISTS accounts(code TEXT PRIMARY KEY,label TEXT NOT NULL,class TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS journal(
          id INTEGER PRIMARY KEY AUTOINCREMENT,jdate TEXT,journal TEXT,piece TEXT,label TEXT,
          account TEXT,debit REAL DEFAULT 0,credit REAL DEFAULT 0,entry_id INTEGER,created TEXT);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
        """)
        defaults = [
          ("401","Fournisseurs","4"),("411","Clients","4"),("44566","TVA déductible","4"),
          ("44571","TVA collectée","4"),("512","Banque","5"),("530","Caisse","5"),
          ("601","Achats matières premières / alimentation","6"),("602","Autres approvisionnements","6"),
          ("606","Achats non stockés","6"),("607","Achats de marchandises","6"),
          ("613","Locations","6"),("615","Entretien et réparations","6"),("616","Assurances","6"),
          ("622","Honoraires","6"),("625","Déplacements","6"),("626","Téléphone / Internet","6"),
          ("627","Services bancaires","6"),("635","Impôts et taxes","6"),("641","Rémunérations","6"),
          ("645","Charges sociales","6"),("681","Dotations aux amortissements","6"),
          ("701","Ventes de produits finis","7"),("707","Ventes de marchandises","7"),("708","Produits annexes","7")]
        c.executemany("INSERT OR IGNORE INTO accounts VALUES(?,?,?)", defaults)

def backup():
    if DB.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = BACKUPS / f"compta_canard_{stamp}.db"
        shutil.copy2(DB, target)
        return target
    return None

def account_for_category(cat, kind):
    mapping = {"Canards / animaux":"601","Aliment":"601","Vétérinaire / sanitaire":"601",
      "Bocaux":"602","Étiquettes":"602","Emballages":"602","Électricité":"606","Eau":"606",
      "Carburant":"606","Matériel":"602","Bâtiment / aménagement":"615","Transport":"625",
      "Assurances":"616","Téléphone / Internet":"626","Comptabilité":"622","Autres":"606"}
    return mapping.get(cat, "601" if kind == "Achat" else "701")

def post_invoice(row):
    with db() as c:
        c.execute("DELETE FROM journal WHERE entry_id=?", (row["id"],))
        d = row["date"] or date.today().isoformat()
        piece = row["number"] or str(row["id"])
        stamp = datetime.now().isoformat()
        if row["kind"] == "Achat":
            lines = [(account_for_category(row["category"],"Achat"),row["ht"],0,row["party"] or "Achat"),
                     ("44566",row["vat"],0,"TVA déductible"),("401",0,row["ttc"],row["party"] or "Fournisseur")]
            journal = "ACH"
        else:
            lines = [("411",row["ttc"],0,row["party"] or "Client"),
                     (account_for_category(row["category"],"Vente"),0,row["ht"],row["party"] or "Vente"),
                     ("44571",0,row["vat"],"TVA collectée")]
            journal = "VTE"
        for account,debit,credit,label in lines:
            if debit or credit:
                c.execute("""INSERT INTO journal(jdate,journal,piece,label,account,debit,credit,entry_id,created)
                             VALUES(?,?,?,?,?,?,?,?,?)""",
                          (d,journal,piece,label,account,debit,credit,row["id"],stamp))

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} — v{VERSION}")
        self.geometry("1180x720"); self.minsize(980,600); self.configure(bg="#f4f6f8")
        self.style = ttk.Style(self); self.style.theme_use("clam")
        self.style.configure("TButton",font=("Segoe UI",10),padding=8,background="#ffffff",foreground="#173a63")
        self.style.map("TButton",background=[("active","#e7f1eb")],foreground=[("active","#173a63")])
        self.style.configure("Treeview",font=("Segoe UI",10),rowheight=31,background="#ffffff",fieldbackground="#ffffff",foreground="#243447")
        self.style.configure("Treeview.Heading",font=("Segoe UI",10,"bold"),background="#e8eef4",foreground="#173a63",padding=8)
        self.style.configure("TNotebook",background="#f4f6f8",borderwidth=0)
        self.style.configure("TNotebook.Tab",font=("Segoe UI",10,"bold"),padding=(14,8))
        self.style.map("TNotebook.Tab",background=[("selected","#ffffff")],foreground=[("selected","#173a63")])
        self.body = tk.Frame(self,bg="#f4f6f8")
        self.topbar()
        self.body.pack(fill="both",expand=True)
        self.dashboard()

    def topbar(self):
        bar=tk.Frame(self,bg="#102b49",height=68); bar.pack(fill="x"); bar.pack_propagate(False)
        brand=tk.Frame(bar,bg="#102b49"); brand.pack(side="left",fill="y",padx=(18,20))
        tk.Label(brand,text="🦆",bg="#102b49",fg="white",font=("Segoe UI Emoji",21)).pack(side="left",padx=(0,8))
        tk.Label(brand,text="COMPTA CANARD",bg="#102b49",fg="white",font=("Segoe UI",14,"bold")).pack(side="left")
        nav=tk.Frame(bar,bg="#102b49"); nav.pack(side="left",fill="y")
        self.nav_buttons=[]
        for label,fn in [("Tableau de bord",self.dashboard),("Factures",self.invoices),
                         ("Grand livre",self.ledger),("Balance",self.balance),("Résultat / EBE",self.reports),
                         ("Paramètres",self.settings)]:
            b=tk.Button(nav,text=label,command=lambda f=fn,l=label:(self.set_active_nav(l),f()),
                      bg="#102b49",fg="#eaf0f6",activebackground="#1d466b",
                      activeforeground="white",relief="flat",bd=0,font=("Segoe UI",9,"bold"),padx=11,cursor="hand2")
            b.pack(side="left",fill="y",pady=5); self.nav_buttons.append((label,b))
        self.set_active_nav("Tableau de bord")

    def set_active_nav(self,active):
        for label,button in getattr(self,"nav_buttons",[]):
            selected=(label==active)
            button.configure(bg="#1d466b" if selected else "#102b49",fg="#ffffff" if selected else "#eaf0f6",
                             highlightthickness=0,relief="flat")

    def clear(self):
        for w in self.body.winfo_children(): w.destroy()

    def heading(self,title,subtitle=""):
        f=tk.Frame(self.body,bg="#f4f6f8"); f.pack(fill="x",padx=26,pady=(20,10))
        tk.Label(f,text=title,bg="#f4f6f8",fg="#102b49",font=("Segoe UI",22,"bold")).pack(anchor="w")
        if subtitle: tk.Label(f,text=subtitle,bg="#f4f6f8",fg="#718096",font=("Segoe UI",10)).pack(anchor="w",pady=(3,0))

    def dashboard(self):
        self.clear(); self.heading("Tableau de bord","Synthèse des factures enregistrées")
        with db() as c:
            r=c.execute("""SELECT
              COALESCE(SUM(CASE WHEN kind='Vente' AND status!='À contrôler' THEN ht ELSE 0 END),0) ca,
              COALESCE(SUM(CASE WHEN kind='Achat' AND status!='À contrôler' THEN ht ELSE 0 END),0) achats,
              COALESCE(SUM(CASE WHEN kind='Vente' AND status!='À contrôler' THEN vat ELSE 0 END),0) vc,
              COALESCE(SUM(CASE WHEN kind='Achat' AND status!='À contrôler' THEN vat ELSE 0 END),0) vd
              FROM entries""").fetchone()
            pending=c.execute("SELECT COUNT(*) FROM entries WHERE status='À contrôler'").fetchone()[0]
        cards=[("Chiffre d'affaires HT",r["ca"]),("Achats HT",r["achats"]),("TVA collectée",r["vc"]),
               ("TVA déductible",r["vd"]),("Factures à contrôler",pending)]
        row=tk.Frame(self.body,bg="#f4f6f8"); row.pack(fill="x",padx=18,pady=8)
        for label,value in cards:
            box=tk.Frame(row,bg="white",highlightbackground="#d9e0e7",highlightthickness=1)
            box.pack(side="left",fill="both",expand=True,padx=5)
            tk.Label(box,text=label,bg="white",fg="#66727e",font=("Segoe UI",9)).pack(anchor="w",padx=12,pady=(12,2))
            val=(str(value) if label=="Factures à contrôler" else money(value)+" €")
            tk.Label(box,text=val,bg="white",fg="#173a63",font=("Segoe UI",16,"bold")).pack(anchor="w",padx=12,pady=(0,12))
        lower=tk.Frame(self.body,bg="#f4f6f8"); lower.pack(fill="both",expand=True,padx=24,pady=(8,18))
        chartbox=tk.Frame(lower,bg="white",highlightbackground="#d9e0e7",highlightthickness=1)
        chartbox.pack(side="left",fill="both",expand=True,padx=(0,8))
        tk.Label(chartbox,text="Activité des 6 derniers mois",bg="white",fg="#173a63",font=("Segoe UI",12,"bold")).pack(anchor="w",padx=16,pady=(14,4))
        canvas=tk.Canvas(chartbox,bg="white",height=235,highlightthickness=0)
        canvas.pack(fill="both",expand=True,padx=12,pady=8)
        with db() as c:
            monthly=c.execute("""SELECT substr(date,1,7) mois,
                SUM(CASE WHEN kind='Vente' AND status!='À contrôler' THEN ht ELSE 0 END) ventes,
                SUM(CASE WHEN kind='Achat' AND status!='À contrôler' THEN ht ELSE 0 END) achats
                FROM entries WHERE date >= ? GROUP BY substr(date,1,7) ORDER BY mois""",
                ((date.today().replace(day=1)-timedelta(days=155)).isoformat(),)).fetchall()
        values={r["mois"]:(float(r["ventes"] or 0),float(r["achats"] or 0)) for r in monthly}
        months=[]
        for offset in range(5,-1,-1):
            first=date.today().replace(day=1)-timedelta(days=offset*30)
            key=first.strftime("%Y-%m")
            if key not in [m[0] for m in months]: months.append((key,values.get(key,(0,0))))
        def draw_chart(_event=None):
            canvas.delete("all")
            width=max(canvas.winfo_width(),360); height=max(canvas.winfo_height(),210)
            left,right,top,bottom=42,width-15,18,height-35
            maxval=max([max(pair) for _,pair in months]+[1])
            canvas.create_line(left,top,left,bottom,fill="#dce4eb")
            canvas.create_line(left,bottom,right,bottom,fill="#dce4eb")
            for i,(month,pair) in enumerate(months):
                center=left+((i+0.5)*(right-left)/6)
                for j,val in enumerate(pair):
                    barh=(bottom-top)*val/maxval
                    x=center-15+j*16
                    canvas.create_rectangle(x,bottom-barh,x+12,bottom,fill=("#239b68" if j==0 else "#8aa4bd"),outline="")
                canvas.create_text(center,bottom+15,text=month[5:],fill="#718096",font=("Segoe UI",8))
            canvas.create_text(left+5,top,text="Ventes",anchor="w",fill="#239b68",font=("Segoe UI",8,"bold"))
            canvas.create_text(left+58,top,text="Achats",anchor="w",fill="#8aa4bd",font=("Segoe UI",8,"bold"))
        canvas.bind("<Configure>",draw_chart); canvas.after(80,draw_chart)
        side=tk.Frame(lower,bg="white",width=285,highlightbackground="#d9e0e7",highlightthickness=1)
        side.pack(side="right",fill="y",padx=(8,0)); side.pack_propagate(False)
        tk.Label(side,text="À retenir",bg="white",fg="#173a63",font=("Segoe UI",12,"bold")).pack(anchor="w",padx=16,pady=(14,10))
        tk.Label(side,text=f"{pending} facture(s) à contrôler",bg="#eaf5ef",fg="#19734b",font=("Segoe UI",10,"bold"),padx=10,pady=9).pack(fill="x",padx=14,pady=4)
        tk.Label(side,text="Les factures importées restent « À contrôler » jusqu'à votre validation. Seules les factures validées alimentent les états comptables.",bg="white",fg="#4f5b66",font=("Segoe UI",10),wraplength=245,justify="left").pack(anchor="w",padx=16,pady=12)
        tk.Label(side,text="Données conservées sur cet ordinateur.",bg="white",fg="#239b68",font=("Segoe UI",9,"bold"),wraplength=245).pack(anchor="w",padx=16,pady=(4,12))

    def invoices(self):
        self.clear(); self.heading("Factures","Importez vos PDF/images, puis vérifiez chaque facture")
        actions=tk.Frame(self.body,bg="#f4f6f8"); actions.pack(fill="x",padx=24)
        ttk.Button(actions,text="📥 Importer des factures",command=self.import_files).pack(side="left")
        ttk.Button(actions,text="🔗 Connecter Outlook",command=self.connect_outlook).pack(side="left",padx=7)
        ttk.Button(actions,text="📨 Récupérer mes factures",command=self.import_from_outlook).pack(side="left",padx=7)
        ttk.Button(actions,text="☁️ Outlook Microsoft",command=self.connect_outlook_graph).pack(side="left",padx=7)
        ttk.Button(actions,text="➕ Nouvelle écriture",command=lambda:self.edit_entry(None)).pack(side="left",padx=7)
        ttk.Button(actions,text="📤 Export CSV",command=self.export_csv).pack(side="left")
        cols=("id","kind","party","number","date","category","ht","vat","ttc","status")
        tree=ttk.Treeview(self.body,columns=cols,show="headings")
        heads=("ID","Type","Tiers","N° pièce","Date","Catégorie","HT","TVA","TTC","Statut")
        for col,label in zip(cols,heads): tree.heading(col,text=label); tree.column(col,width=90)
        tree.column("party",width=155); tree.column("category",width=145)
        tree.pack(fill="both",expand=True,padx=24,pady=12)
        with db() as c: rows=c.execute("SELECT * FROM entries ORDER BY date DESC,id DESC").fetchall()
        for r in rows:
            tree.insert("", "end",values=(r["id"],r["kind"],r["party"],r["number"],r["date"],r["category"],
                money(r["ht"]),money(r["vat"]),money(r["ttc"]),r["status"]))
        def open_selected(_=None):
            sel=tree.selection()
            if sel: self.edit_entry(tree.item(sel[0])["values"][0])
        tree.bind("<Double-1>",open_selected)

    def connect_outlook(self):
        """Teste la connexion au profil Outlook classique sans modifier les e-mails."""
        try:
            import win32com.client
        except ImportError:
            messagebox.showerror("Outlook indisponible",
                "Le module de connexion Outlook n'est pas installé dans Python (pywin32).")
            return
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            namespace = outlook.GetNamespace("MAPI")
            inbox = namespace.GetDefaultFolder(6)
            profile = getattr(namespace, "CurrentProfileName", "") or "Profil Outlook"
            account_names = []
            try:
                accounts = namespace.Accounts
                for i in range(1, accounts.Count + 1):
                    name = str(getattr(accounts.Item(i), "DisplayName", "") or "").strip()
                    if name:
                        account_names.append(name)
            except Exception:
                pass
            details = f"Profil : {profile}\nBoîte de réception : {inbox.Name}"
            if account_names:
                details += "\nCompte(s) détecté(s) :\n• " + "\n• ".join(account_names)
            messagebox.showinfo("Outlook connecté",
                "La connexion à Outlook classique fonctionne.\n\n" + details +
                "\n\nLe bouton « Récupérer mes factures » peut maintenant rechercher les pièces jointes.")
        except Exception as e:
            messagebox.showerror("Connexion Outlook impossible",
                "Compta Canard ne peut pas accéder au profil Outlook classique.\n\n"
                "Si vous utilisez le nouvel Outlook, cette connexion COM n'est pas disponible : "
                "le nouvel Outlook utilise une intégration Microsoft Graph différente.\n\n" + str(e))

    def get_graph_client_id(self):
        with db() as c:
            row = c.execute("SELECT value FROM settings WHERE key='graph_client_id'").fetchone()
        return (row["value"].strip() if row and row["value"] else "")

    def set_graph_client_id(self, client_id):
        with db() as c:
            c.execute("INSERT INTO settings(key,value) VALUES('graph_client_id',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (client_id.strip(),))

    def configure_outlook_graph(self):
        w=tk.Toplevel(self); w.title("Connexion Outlook Microsoft"); w.geometry("650x330"); w.transient(self)
        tk.Label(w,text="Connexion au nouvel Outlook",font=("Segoe UI",16,"bold"),fg="#102b49").pack(anchor="w",padx=22,pady=(20,8))
        tk.Label(w,text="Le nouvel Outlook utilise Microsoft Graph. Une application Microsoft Entra doit être créée une seule fois pour autoriser Compta Canard à lire les e-mails et leurs pièces jointes.",wraplength=600,justify="left").pack(anchor="w",padx=22)
        tk.Label(w,text="ID d’application (client) :",font=("Segoe UI",10,"bold")).pack(anchor="w",padx=22,pady=(18,4))
        v=tk.StringVar(value=self.get_graph_client_id())
        ttk.Entry(w,textvariable=v,width=55).pack(anchor="w",padx=22)
        def open_portal():
            webbrowser.open("https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade")
        ttk.Button(w,text="🌐 Ouvrir Microsoft Entra",command=open_portal).pack(anchor="w",padx=22,pady=10)
        tk.Label(w,text="Après création de l’application, activez le flux appareil (public client) et ajoutez la permission déléguée Mail.Read.",fg="#66727e",wraplength=600,justify="left").pack(anchor="w",padx=22)
        def save():
            cid=v.get().strip()
            if not cid:
                messagebox.showerror("ID manquant","Renseignez l’ID d’application (client).",parent=w); return
            self.set_graph_client_id(cid); w.destroy()
            messagebox.showinfo("Configuration enregistrée","L’ID Microsoft est enregistré sur cet ordinateur. Vous pouvez maintenant tester la connexion Outlook Microsoft.")
        ttk.Button(w,text="💾 Enregistrer",command=save).pack(anchor="e",padx=22,pady=14)

    def graph_request(self, url, token):
        req=urllib.request.Request(url,headers={"Authorization":"Bearer "+token,"Accept":"application/json","User-Agent":"ComptaCanard/2.2"})
        with urllib.request.urlopen(req,timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def connect_outlook_graph(self):
        client_id=self.get_graph_client_id()
        if not client_id:
            self.configure_outlook_graph(); return
        try:
            import msal
        except ImportError:
            messagebox.showerror("Module manquant","Le module Microsoft MSAL n'est pas installé dans Python.\n\nInstallez-le avec :\npy -m pip install msal"); return
        try:
            app=msal.PublicClientApplication(client_id,authority="https://login.microsoftonline.com/common")
            flow=app.initiate_device_flow(scopes=["Mail.Read"])
            if "user_code" not in flow: raise RuntimeError("Microsoft n'a pas fourni de code de connexion.")
            messagebox.showinfo("Connexion Microsoft","Une fenêtre de navigateur va s'ouvrir. Connectez-vous avec votre compte Outlook/Hotmail, puis revenez dans Compta Canard.\n\nCode : "+flow["user_code"])
            webbrowser.open(flow["verification_uri"])
            result=app.acquire_token_by_device_flow(flow)
            if "access_token" not in result: raise RuntimeError(result.get("error_description","Connexion Microsoft refusée."))
            data=self.graph_request("https://graph.microsoft.com/v1.0/me?$select=displayName,mail,userPrincipalName",result["access_token"])
            name=data.get("displayName") or data.get("mail") or data.get("userPrincipalName") or "Compte Microsoft"
            messagebox.showinfo("Outlook Microsoft connecté","Connexion réussie à : "+name+"\n\nLa connexion au nouvel Outlook fonctionne.")
        except Exception as e:
            messagebox.showerror("Connexion Microsoft impossible","La connexion au nouvel Outlook n'a pas abouti.\n\n"+str(e))

    def import_from_outlook_graph(self):
        client_id=self.get_graph_client_id()
        if not client_id:
            self.configure_outlook_graph(); return
        try:
            import msal, base64
        except ImportError:
            messagebox.showerror("Module manquant","Le module Microsoft MSAL n'est pas installé dans Python.\n\nInstallez-le avec :\npy -m pip install msal"); return
        try:
            app=msal.PublicClientApplication(client_id,authority="https://login.microsoftonline.com/common")
            flow=app.initiate_device_flow(scopes=["Mail.Read"])
            if "user_code" not in flow: raise RuntimeError("Microsoft n'a pas fourni de code de connexion.")
            messagebox.showinfo("Connexion Microsoft","Connectez-vous avec votre compte Outlook/Hotmail.\n\nCode : "+flow["user_code"])
            webbrowser.open(flow["verification_uri"])
            result=app.acquire_token_by_device_flow(flow)
            if "access_token" not in result: raise RuntimeError(result.get("error_description","Connexion Microsoft refusée."))
            cutoff=(datetime.now()-timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
            url="https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$top=50&$select=id,subject,receivedDateTime,hasAttachments&$filter=receivedDateTime ge "+cutoff+" and hasAttachments eq true"
            imported=duplicates=errors=0; known_hashes=set()
            for existing in DOCS.iterdir():
                if existing.is_file():
                    try: known_hashes.add(hashlib.sha256(existing.read_bytes()).hexdigest())
                    except OSError: pass
            while url:
                data=self.graph_request(url,result["access_token"])
                for msg in data.get("value",[]):
                    try:
                        atts=self.graph_request("https://graph.microsoft.com/v1.0/me/messages/"+msg["id"]+"/attachments",result["access_token"])
                        for att in atts.get("value",[]):
                            if att.get("@odata.type")!="#microsoft.graph.fileAttachment": continue
                            name=str(att.get("name") or "piece_jointe"); suffix=Path(name).suffix.lower()
                            if suffix not in {".pdf",".png",".jpg",".jpeg",".webp"}: continue
                            raw=att.get("contentBytes")
                            if not raw: continue
                            data_bytes=base64.b64decode(raw); digest=hashlib.sha256(data_bytes).hexdigest()
                            if digest in known_hashes: duplicates+=1; continue
                            safe=re.sub(r"[^A-Za-z0-9._-]+","_",Path(name).name).strip("._") or ("facture"+suffix)
                            dest=DOCS/(datetime.now().strftime("%Y%m%d_%H%M%S_%f_")+safe); dest.write_bytes(data_bytes); known_hashes.add(digest)
                            received=(msg.get("receivedDateTime") or "")[:10] or date.today().isoformat()
                            with db() as c:
                                c.execute("""INSERT INTO entries(kind,party,number,date,category,ht,rate,vat,ttc,status,notes,file,created)
                                             VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                          ("Achat","À renseigner",Path(name).stem,received,"Autres",0,20,0,0,"À contrôler",
                                           "Pièce jointe récupérée depuis le nouvel Outlook via Microsoft Graph. Vérifier le fournisseur, la date et les montants.",
                                           str(dest),datetime.now().isoformat()))
                            imported+=1
                    except Exception: errors+=1
                url=data.get("@odata.nextLink")
            messagebox.showinfo("Récupération Outlook Microsoft terminée",f"Factures/pièces jointes importées : {imported}\nDoublons ignorés : {duplicates}\nÉléments non récupérés : {errors}\n\nLes fichiers importés sont « À contrôler »."); self.invoices()
        except Exception as e:
            messagebox.showerror("Récupération Outlook Microsoft impossible","La récupération n'a pas abouti.\n\n"+str(e))

    def import_from_outlook(self):
        """Récupère les pièces jointes de facture depuis Outlook classique (profil déjà connecté)."""
        try:
            import win32com.client
        except ImportError:
            messagebox.showerror("Outlook indisponible",
                "Le composant Outlook n'est pas présent dans cette version. Une mise à jour est nécessaire.")
            return
        if not messagebox.askyesno("Récupération Outlook",
            "Rechercher les PDF et images joints aux e-mails reçus dans la boîte de réception "
            "et ses sous-dossiers au cours des 12 derniers mois ?\n\n"
            "Les fichiers seront importés « À contrôler » et aucun e-mail ne sera modifié."):
            return
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            namespace = outlook.GetNamespace("MAPI")
            inbox = namespace.GetDefaultFolder(6)
        except Exception as e:
            messagebox.showerror("Connexion Outlook impossible",
                "Impossible d'accéder au profil Outlook classique.\n"
                "Vérifiez qu'Outlook est ouvert et que votre compte est connecté.\n\n" + str(e))
            return

        allowed = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
        cutoff = datetime.now() - timedelta(days=365)
        known_hashes = set()
        for existing in DOCS.iterdir():
            if existing.is_file():
                try:
                    h = hashlib.sha256(existing.read_bytes()).hexdigest()
                    known_hashes.add(h)
                except OSError:
                    pass

        imported = 0
        duplicates = 0
        errors = 0

        def scan_folder(folder):
            nonlocal imported, duplicates, errors
            try:
                items = folder.Items
                for item in items:
                    try:
                        if getattr(item, "Class", None) != 43:
                            continue
                        received = item.ReceivedTime
                        if received and received.replace(tzinfo=None) < cutoff:
                            continue
                        attachments = item.Attachments
                        for index in range(1, attachments.Count + 1):
                            attachment = attachments.Item(index)
                            original = str(attachment.FileName or "piece_jointe")
                            suffix = Path(original).suffix.lower()
                            if suffix not in allowed:
                                continue
                            safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(original).name).strip("._")
                            if not safe:
                                safe = "facture" + suffix
                            dest = DOCS / (datetime.now().strftime("%Y%m%d_%H%M%S_%f_") + safe)
                            try:
                                attachment.SaveAsFile(str(dest))
                                digest = hashlib.sha256(dest.read_bytes()).hexdigest()
                                if digest in known_hashes:
                                    dest.unlink(missing_ok=True)
                                    duplicates += 1
                                    continue
                                known_hashes.add(digest)
                                with db() as c:
                                    c.execute("""INSERT INTO entries(kind,party,number,date,category,ht,rate,vat,ttc,
                                                 status,notes,file,created)
                                                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                        ("Achat", "À renseigner", Path(original).stem,
                                         date.today().isoformat(), "Autres", 0, 20, 0, 0,
                                         "À contrôler",
                                         "Pièce jointe récupérée depuis Outlook. Vérifier le fournisseur, la date et les montants.",
                                         str(dest), datetime.now().isoformat()))
                                imported += 1
                            except Exception:
                                errors += 1
                                try:
                                    dest.unlink(missing_ok=True)
                                except Exception:
                                    pass
                    except Exception:
                        errors += 1
                try:
                    for subfolder in folder.Folders:
                        scan_folder(subfolder)
                except Exception:
                    pass
            except Exception:
                errors += 1

        scan_folder(inbox)
        messagebox.showinfo("Récupération terminée",
            f"Factures/pièces jointes importées : {imported}\n"
            f"Doublons ignorés : {duplicates}\n"
            f"Éléments non récupérés : {errors}\n\n"
            "Les fichiers importés sont « À contrôler ».")
        self.invoices()

    def import_files(self):
        files=filedialog.askopenfilenames(title="Choisir les factures",
          filetypes=[("PDF et images","*.pdf *.png *.jpg *.jpeg *.webp"),("Tous les fichiers","*.*")])
        if not files: return
        imported=0
        with db() as c:
            for src in files:
                p=Path(src); dest=DOCS/(datetime.now().strftime("%Y%m%d_%H%M%S_%f_")+p.name)
                shutil.copy2(p,dest)
                c.execute("""INSERT INTO entries(kind,party,number,date,category,ht,rate,vat,ttc,status,notes,file,created)
                             VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    ("Achat","À renseigner",p.stem,date.today().isoformat(),"Autres",0,20,0,0,
                     "À contrôler","Facture importée : renseigner et vérifier les montants.",str(dest),datetime.now().isoformat()))
                imported+=1
        messagebox.showinfo("Import terminé",f"{imported} facture(s) importée(s). Elles restent à contrôler.")
        self.invoices()

    def edit_entry(self,entry_id):
        w=tk.Toplevel(self); w.title("Facture / écriture"); w.geometry("570x600"); w.transient(self)
        fields=["kind","party","number","date","due","category","ht","rate","payment","status","notes"]
        v={k:tk.StringVar() for k in fields}
        v["kind"].set("Achat"); v["date"].set(date.today().isoformat()); v["rate"].set("20")
        v["category"].set("Autres"); v["status"].set("À contrôler")
        with db() as c: old=c.execute("SELECT * FROM entries WHERE id=?",(entry_id,)).fetchone() if entry_id else None
        if old:
            for k in fields:
                if old[k] is not None: v[k].set(str(old[k]))
        frm=tk.Frame(w,padx=18,pady=15); frm.pack(fill="both",expand=True)
        categories=["Canards / animaux","Aliment","Vétérinaire / sanitaire","Matériel","Bâtiment / aménagement",
                    "Bocaux","Étiquettes","Emballages","Électricité","Eau","Carburant","Transport",
                    "Assurances","Téléphone / Internet","Comptabilité","Autres"]
        for i,(label,key) in enumerate(zip(["Type","Tiers","N° pièce","Date AAAA-MM-JJ","Échéance","Catégorie",
                    "Montant HT","Taux TVA (%)","Paiement","Statut","Notes"],fields)):
            tk.Label(frm,text=label).grid(row=i,column=0,sticky="w",pady=5)
            if key=="kind": widget=ttk.Combobox(frm,textvariable=v[key],values=["Achat","Vente"],state="readonly")
            elif key=="category": widget=ttk.Combobox(frm,textvariable=v[key],values=categories,state="readonly")
            elif key=="status": widget=ttk.Combobox(frm,textvariable=v[key],values=["À contrôler","Validée","Payée","Partiellement payée"],state="readonly")
            else: widget=ttk.Entry(frm,textvariable=v[key],width=38)
            widget.grid(row=i,column=1,sticky="ew")
        frm.columnconfigure(1,weight=1)
        def save():
            try:
                ht=float(v["ht"].get().replace(",",".") or 0); rate=float(v["rate"].get().replace(",",".") or 0)
                if ht<0 or rate<0: raise ValueError()
                vat=round(ht*rate/100,2); ttc=round(ht+vat,2)
                datetime.strptime(v["date"].get(),"%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Valeur incorrecte","Vérifiez le montant HT, le taux de TVA et la date (AAAA-MM-JJ)."); return
            now=datetime.now().isoformat()
            with db() as c:
                values=(v["kind"].get(),v["party"].get(),v["number"].get(),v["date"].get(),v["due"].get(),
                        v["category"].get(),ht,rate,vat,ttc,v["payment"].get(),v["status"].get(),v["notes"].get(),now)
                if entry_id:
                    c.execute("""UPDATE entries SET kind=?,party=?,number=?,date=?,due=?,category=?,ht=?,rate=?,
                      vat=?,ttc=?,payment=?,status=?,notes=?,created=? WHERE id=?""",values+(entry_id,))
                    current_id=entry_id
                else:
                    cur=c.execute("""INSERT INTO entries(kind,party,number,date,due,category,ht,rate,vat,ttc,
                      payment,status,notes,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",values)
                    current_id=cur.lastrowid
                row=c.execute("SELECT * FROM entries WHERE id=?",(current_id,)).fetchone()
            if row["status"] in ("Validée","Payée","Partiellement payée"): post_invoice(row)
            else:
                with db() as c: c.execute("DELETE FROM journal WHERE entry_id=?",(current_id,))
            w.destroy(); self.invoices()
        ttk.Button(frm,text="💾 Enregistrer",command=save).grid(row=len(fields),column=1,sticky="e",pady=14)

    def ledger(self):
        self.clear(); self.heading("Grand livre","Écritures comptables des factures validées")
        cols=("date","journal","piece","label","account","debit","credit")
        tree=ttk.Treeview(self.body,columns=cols,show="headings")
        for col,label in zip(cols,["Date","Journal","Pièce","Libellé","Compte","Débit","Crédit"]):
            tree.heading(col,text=label); tree.column(col,width=115)
        tree.column("label",width=280); tree.pack(fill="both",expand=True,padx=24,pady=12)
        with db() as c: rows=c.execute("SELECT * FROM journal ORDER BY jdate,account,id").fetchall()
        for r in rows: tree.insert("", "end",values=(r["jdate"],r["journal"],r["piece"],r["label"],r["account"],money(r["debit"]),money(r["credit"])))

    def balance(self):
        self.clear(); self.heading("Balance générale","Totaux débit/crédit et solde par compte")
        cols=("account","label","debit","credit","balance")
        tree=ttk.Treeview(self.body,columns=cols,show="headings")
        for col,label in zip(cols,["Compte","Libellé","Total débit","Total crédit","Solde"]):
            tree.heading(col,text=label); tree.column(col,width=145)
        tree.column("label",width=340); tree.pack(fill="both",expand=True,padx=24,pady=12)
        with db() as c:
            rows=c.execute("""SELECT j.account,COALESCE(a.label,'Compte') label,SUM(j.debit) debit,SUM(j.credit) credit
                              FROM journal j LEFT JOIN accounts a ON a.code=j.account
                              GROUP BY j.account ORDER BY j.account""").fetchall()
        for r in rows:
            tree.insert("", "end",values=(r["account"],r["label"],money(r["debit"]),money(r["credit"]),money(r["debit"]-r["credit"])))

    def reports(self):
        self.clear(); self.heading("Résultat / EBE / TVA","Indicateurs simplifiés à partir des factures validées")
        with db() as c:
            ca=c.execute("SELECT COALESCE(SUM(ht),0) FROM entries WHERE kind='Vente' AND status!='À contrôler'").fetchone()[0]
            achats=c.execute("SELECT COALESCE(SUM(ht),0) FROM entries WHERE kind='Achat' AND status!='À contrôler'").fetchone()[0]
            vc=c.execute("SELECT COALESCE(SUM(vat),0) FROM entries WHERE kind='Vente' AND status!='À contrôler'").fetchone()[0]
            vd=c.execute("SELECT COALESCE(SUM(vat),0) FROM entries WHERE kind='Achat' AND status!='À contrôler'").fetchone()[0]
        tabs=ttk.Notebook(self.body); tabs.pack(fill="both",expand=True,padx=24,pady=12)
        f=tk.Frame(tabs,bg="white"); tabs.add(f,text="Compte de résultat")
        for i,(label,val) in enumerate([("Chiffre d'affaires",ca),("Achats saisis",achats),("Solde simplifié",ca-achats)]):
            tk.Label(f,text=label,bg="white",font=("Segoe UI",12,"bold" if i==2 else "normal")).grid(row=i,column=0,sticky="w",padx=20,pady=12)
            tk.Label(f,text=money(val)+" €",bg="white",font=("Segoe UI",12,"bold")).grid(row=i,column=1,padx=20)
        f=tk.Frame(tabs,bg="white"); tabs.add(f,text="EBE indicatif")
        tk.Label(f,text=money(ca-achats)+" €",bg="white",fg="#173a63",font=("Segoe UI",27,"bold")).pack(anchor="w",padx=22,pady=20)
        tk.Label(f,text="Estimation très simplifiée : elle ne remplace pas un EBE comptable. Les stocks, amortissements, aides, salaires, cotisations et retraitements doivent être traités avec l'expert-comptable.",bg="white",fg="#66727e",wraplength=850,justify="left").pack(anchor="w",padx=22)
        f=tk.Frame(tabs,bg="white"); tabs.add(f,text="TVA")
        for i,(label,val) in enumerate([("TVA collectée",vc),("TVA déductible",vd),("TVA nette",vc-vd)]):
            tk.Label(f,text=label,bg="white").grid(row=i,column=0,sticky="w",padx=20,pady=12)
            tk.Label(f,text=money(val)+" €",bg="white",font=("Segoe UI",11,"bold")).grid(row=i,column=1,padx=20)

    def export_csv(self):
        dest=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")],initialfile="compta_canard.csv")
        if not dest:return
        with db() as c: rows=c.execute("SELECT * FROM entries ORDER BY date,id").fetchall()
        with open(dest,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f,delimiter=";")
            w.writerow(rows[0].keys() if rows else ["id"])
            for r in rows: w.writerow(list(r))
        messagebox.showinfo("Export","Export CSV terminé.")

    def settings(self):
        self.clear(); self.heading("Paramètres","Sécurité et emplacement des données")
        box=tk.Frame(self.body,bg="white",highlightbackground="#d9e0e7",highlightthickness=1)
        box.pack(fill="x",padx=24,pady=12)
        tk.Label(box,text=f"Version installée : {VERSION}",bg="white",font=("Segoe UI",12,"bold")).pack(anchor="w",padx=18,pady=12)
        tk.Label(box,text=f"Dossier des données : {BASE}",bg="white",fg="#66727e").pack(anchor="w",padx=18)
        ttk.Button(box,text="🔄 Rechercher les mises à jour",command=self.check_for_updates).pack(anchor="w",padx=18,pady=(14,6))
        ttk.Button(box,text="💾 Sauvegarder maintenant",command=self.do_backup).pack(anchor="w",padx=18,pady=6)
        ttk.Button(box,text="📂 Ouvrir le dossier des données",command=self.open_data).pack(anchor="w",padx=18,pady=(0,14))
        tk.Label(box,text="Les mises à jour du programme ne doivent jamais supprimer ce dossier.",bg="white",fg="#2d7d46").pack(anchor="w",padx=18,pady=(0,14))

    def check_for_updates(self):
        """Vérifie une mise à jour publique et l'installe après sauvegarde locale."""
        if getattr(sys, "frozen", False):
            messagebox.showinfo("Mise à jour",
                "Le mécanisme de mise à jour automatique sera disponible dans la version Python (.py).")
            return
        script = Path(__file__).resolve()
        manifest_url = "https://raw.githubusercontent.com/jeffoux40/compta-canard-updates/main/manifest.json"
        try:
            request = urllib.request.Request(manifest_url, headers={"User-Agent": "ComptaCanard-Updater/1.0"})
            ssl_context = ssl.create_default_context(cafile=certifi.where()) if certifi else ssl.create_default_context()
            with urllib.request.urlopen(request, timeout=15, context=ssl_context) as response:
                manifest = json.loads(response.read().decode("utf-8"))
            latest = str(manifest.get("version", "")).strip()
            current_parts = tuple(int(x) for x in VERSION.split("."))
            latest_parts = tuple(int(x) for x in latest.split("."))
            if len(latest_parts) != 3:
                raise ValueError("Numéro de version distant invalide.")
            if latest_parts <= current_parts:
                messagebox.showinfo("Mise à jour", f"Compta Canard est déjà à jour (v{VERSION}).")
                return
            if not messagebox.askyesno("Mise à jour disponible",
                    f"Version installée : {VERSION}\nNouvelle version : {latest}\n\n"
                    "Une sauvegarde de la base comptable et du programme sera créée avant installation.\n"
                    "Les factures et documents ne seront pas déplacés ni supprimés.\n\n"
                    "Installer cette mise à jour ?"):
                return
            download_url = str(manifest.get("download_url", ""))
            if not download_url.startswith("https://raw.githubusercontent.com/jeffoux40/compta-canard-updates/main/"):
                raise ValueError("Adresse de téléchargement non autorisée.")
            request = urllib.request.Request(download_url, headers={"User-Agent": "ComptaCanard-Updater/1.0"})
            with urllib.request.urlopen(request, timeout=30, context=ssl_context) as response:
                new_code = response.read()
            expected = str(manifest.get("blob_sha1", "")).lower()
            actual = hashlib.sha1(b"blob " + str(len(new_code)).encode("ascii") + b"\0" + new_code).hexdigest()
            if not expected or actual != expected:
                raise ValueError("La vérification d'intégrité du programme a échoué. Rien n'a été installé.")
            compile(new_code, str(script), "exec")
            program_backups = BACKUPS / "programmes"
            program_backups.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            program_backup = program_backups / f"Compta_Canard_{VERSION}_{stamp}.py"
            shutil.copy2(script, program_backup)
            db_backup = None
            if DB.exists():
                db_backup = BACKUPS / f"compta_canard_avant_maj_{stamp}.db"
                with sqlite3.connect(str(DB)) as source_db, sqlite3.connect(str(db_backup)) as target_db:
                    source_db.backup(target_db)
            temp_script = script.with_name(script.name + ".update")
            try:
                temp_script.write_bytes(new_code)
                os.replace(temp_script, script)
            except Exception:
                temp_script.unlink(missing_ok=True)
                raise
            messagebox.showinfo("Mise à jour prête",
                f"Compta Canard va redémarrer en version {latest}.\n\n"
                f"Sauvegarde du programme : {program_backup}\n"
                + (f"Sauvegarde comptable : {db_backup}" if db_backup else
                   "Aucune base comptable n'existait encore."))
            subprocess.Popen([sys.executable, str(script)], cwd=str(script.parent))
            self.destroy()
        except Exception as e:
            messagebox.showerror("Mise à jour impossible",
                "Aucune mise à jour n'a été installée. Votre base comptable et vos factures restent en place.\n\n"
                + str(e))

    def do_backup(self):
        path=backup()
        if path: messagebox.showinfo("Sauvegarde",f"Sauvegarde créée :\n{path}")
        else: messagebox.showinfo("Sauvegarde","Aucune base de données à sauvegarder pour le moment.")

    def open_data(self):
        try:
            if sys.platform=="win32": os.startfile(str(BASE))
            else: messagebox.showinfo("Dossier des données",str(BASE))
        except Exception as e: messagebox.showerror("Erreur",str(e))

if __name__=="__main__":
    init_db()
    App().mainloop()
