# Arch Setup & Package Manager 🧰🐧

Ein multifunktionales Python-GUI-Tool zur schnellen Einrichtung und Verwaltung eines Arch Linux-Systems.  
Entstanden als privates Tool zur Automatisierung von typischen Setup-Schritten nach einer frischen Installation – mit Fokus auf Usability, Effizienz und Übersichtlichkeit.

---

## 🔧 Funktionen

- **„Must-Haves & Hacks“-Tab**  
  ✅ Checkliste typischer Arch-Tools  
  ⚙️ Auto-Install über `pacman`, Git oder Script  
  📊 Fortschrittsanzeige + Logging

- **Pacman Manager**  
  🔍 Paket-Suche (`pacman -Ss`)  
  📥 Ein-Klick-Installation  
  📋 Anzeigen aller installierten Pakete

- **Pip Manager**  
  🔍 Paket-Suche (`pip3 search`)  
  📥 Ein-Klick-Installation  
  📋 Liste installierter Pakete

- **Systeminformationen**  
  🧠 Infos zu OS, Kernel, etc.  
  🔍 Anzeige von `/etc/os-release` und `uname -a`

- **GUI mit PyQt5**  
  🖥️ Moderne Oberfläche  
  🧪 Mit integriertem Logging + dynamischem Feedback

---

## 🚨 Hinweis

- Dieses Tool erfordert **Root-Rechte** beim Start (`sudo`) und prüft das automatisch.
- Es ist **Work-in-Progress** – manche Tools (z. B. `auto-cpufreq`) werden speziell behandelt und per Git installiert.
- Der Fokus liegt auf **Arch Linux / Manjaro / EndeavourOS** – auf anderen Distros nicht getestet.

---

## 📦 Abhängigkeiten

- Python 3
- `PyQt5`
- `git`
- Optional: `yay` oder `paru` für AUR-Pakete

### Installation (wenn nötig):
```bash
sudo pacman -S python-pyqt5 git
