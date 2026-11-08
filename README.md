# Buttergen

A Warrior Cats game where you play as your own cat, every cat has real, inheritable genes so kits look like their parents, and cats come in a huge variety of looks. This is just the beginning, and plenty more features are on the way: see [Planned features](#planned-features) below.

Updated November 8, 2026.

**Buttergen is in early development.** Things will change, and there may be bugs. If you find one, please report it on the [Issues page](https://github.com/Tropicaluwu/Buttergen/issues).

**Join the Discord server** for help, news and bug reports: [discord.gg/Kxdvk5eXC9](https://discord.gg/Kxdvk5eXC9)

I ask that if you make a fork or a version of this mod built off of my code, you credit me as well as the creators of LifeGen, Genemod, LifeGen Genetics, ClanGen and the mods listed under Credits too.

## How to play

Buttergen runs from its source code, so there's no app to install. Instead you install **uv**. After that, starting the game is a double-click (or one command on Linux).

You need an internet connection the first time you start the game: uv downloads the right version of Python and everything the game needs.

> **Important:** your Clans are saved in the **saves** folder inside the game folder. **Every time you download a new version, copy your saves folder into the new game folder**, or your Clans won't be there. See [Updating](#updating-to-a-new-version). The game tells you on the start screen when a new version is out.

Jump to: [Windows](#windows) | [Mac](#mac) | [Linux](#linux) | [Updating](#updating-to-a-new-version) | [Problems](#if-something-goes-wrong)

---

### Windows

**1. Install uv (one time only)**

1. Press the **Windows key**, type **PowerShell** and open it.
2. Copy this line, paste it into the PowerShell window (right-click pastes) and press **Enter**:
   ```
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
3. When it says it's done, close PowerShell.

**2. Download the game**

1. Go to the [Buttergen GitHub page](https://github.com/Tropicaluwu/Buttergen) (the page you're reading this on).
2. Near the top, click the green **Code** button:

   ![The green Code button](readme-images/code-button.png)
3. Click **Download ZIP**:

   ![Download ZIP](readme-images/download-zip.png)
4. Find the zip in your Downloads, right-click it and choose **Extract All**. Put the folder somewhere easy to find, like your Desktop.

**3. Play**

1. Open the folder you extracted and double-click **run.bat**.
2. If Windows says **"Windows protected your PC"**, click **More info**, then **Run anyway**. It only asks the first time.
3. A black window opens and sets things up (the first time takes a minute or two), then the game opens. Keep the black window open while you play.

Next time, just double-click **run.bat** again.

---

### Mac

**1. Install uv (one time only)**

1. Open **Terminal** (press **Cmd + Space**, type **Terminal** and press **Enter**).
2. Copy this line, paste it into Terminal (**Cmd + V**) and press **Enter**:
   ```
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
3. When it says it's done, close Terminal.

**2. Download the game**

1. Go to the [Buttergen GitHub page](https://github.com/Tropicaluwu/Buttergen) (the page you're reading this on).
2. Near the top, click the green **Code** button:

   ![The green Code button](readme-images/code-button.png)
3. Click **Download ZIP**:

   ![Download ZIP](readme-images/download-zip.png)
4. Open the zip from your Downloads (double-click it) to unzip it. Move the folder somewhere easy to find, like your Desktop.

**3. Play**

1. Open the folder and **right-click** (or Control-click) **run.command**, then choose **Open**.
2. Your Mac will warn you that it's from an unidentified developer. Click **Open**.
   - On newer Macs there may be no Open button, only **Done**. Then open **System Settings --> Privacy & Security**, scroll down to the message about **run.command** and click **Open Anyway**, then right-click **run.command** and choose **Open** again.
3. A Terminal window opens and sets things up (the first time takes a minute or two), then the game opens. Keep the Terminal window open while you play.

Next time, just double-click **run.command**.

---

### Linux

**1. Install uv (one time only)**

Open a terminal, paste this and press **Enter**:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```
(No curl? Use `wget -qO- https://astral.sh/uv/install.sh | sh` instead.) Then close the terminal and open a new one.

**2. Download the game**

On the [Buttergen GitHub page](https://github.com/Tropicaluwu/Buttergen), click the green **Code** button, then **Download ZIP**, and unzip it.

**3. Play**

In the terminal, go into the unzipped folder and start the game:
```
cd path/to/the/folder
bash run.sh
```
(Tip: type `cd ` with a space, then drag the folder into the terminal window to fill in its path.)

Some file managers can also start it: right-click **run.sh** and choose **Run as a Program** (or **Run**).

---

### Updating to a new version

When a new version is out, the game shows **Update Available!** on the start screen. Click it to see how to update.

Your saves are inside the game folder, in a folder called **saves**. So **every time** you update, bring them along:

1. Download the new version the same way as the first time (green **Code** button, then **Download ZIP**) and unzip it.
2. Copy the **saves** folder from your old game folder into the new one. If the new folder already has a **saves** folder, replace it.
3. Start the game from the new folder the same way as before.

Once your Clans show up in the new version, you can delete the old folder.

---

### If something goes wrong

- **"uv is not recognized" / "uv: command not found":** close the window and try again. If it still happens, restart your computer. If it still happens even after that, uv didn't install: repeat step 1.
- **The window closes right away (Windows):** right-click inside the game folder, choose **Open in Terminal**, type `.\run.bat` and press **Enter**. The window stays open, so you can see the error.
- **Mac: "run.command can't be opened":** see step 3 for Mac (**Open Anyway** in Privacy & Security).
- **It got stuck or failed the first time:** check your internet connection and start it again. It picks up where it left off.
- **"DLL load failed" (Windows):** install the [Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe), then start the game again.
- **"An Application Control policy has blocked this file" or "python.exe - Bad Image" (Windows 11):** this is Windows Smart App Control, not a broken download. See [Blocked by Smart App Control](#blocked-by-smart-app-control).
- **My Clans are gone after updating:** copy the **saves** folder from the old game folder into the new one (see [Updating](#updating-to-a-new-version)).


### Blocked by Smart App Control

Smart App Control is a Windows 11 security feature that blocks programs it doesn't recognize, and that includes the copy of Python that uv downloads. You might see **"An Application Control policy has blocked this file (os error 4551)"**, or a **"python.exe - Bad Image"** window with **error status 0xc0e90002** that says `python312.dll` is damaged. It isn't damaged, it's being blocked.

**Easiest fix:** open **Windows Security** > **App & browser control** > **Smart App Control** and turn it off, then start the game again. Windows may not let you turn it back on without resetting your PC, so decide if that's okay first.

**If you'd rather keep it on,** you can try playing with the official Python instead of uv. This might not work on every PC, because Windows can still block the game's add-on files.

1. Install **Python 3.12** from [python.org](https://www.python.org/downloads/). Pick a 3.12 version that has a Windows installer, and leave the "py launcher" option ticked.
2. In the game folder, right-click an empty spot and choose **Open in Terminal**. If that isn't there, click the address bar at the top of the folder, type `cmd` and press **Enter**.
3. Run this to remove uv's Python, so it can't get picked by mistake:
   ```
   uv python uninstall 3.12
   ```
4. Run this once to install what the game needs:
   ```
   py -V:PythonCore/3.12 -m pip install "black~=23.0" "cryptography~=42.0" "pgpy~=0.6" "platformdirs~=3.3" "pydantic>=2.12.0" "pygame-ce~=2.2" "pygame-gui~=0.6" "requests~=2.28" "strenum~=0.4" "tomli>=2.2.1" "ujson~=5.7"
   ```
5. Start the game with this line, every time you play:
   ```
   py -V:PythonCore/3.12 main.py
   ```

Don't use `run.bat` for this, because it downloads uv's Python again. To start the game with a double-click, make a text file in the game folder called `play.bat` with these lines in it:
```
@echo off
py -V:PythonCore/3.12 main.py
pause
```

If it's still blocked and the error mentions `Python312\Lib\site-packages`, Windows is blocking the add-on files too. Your options then are turning Smart App Control off, playing on another PC, or using a virtual machine.

---

## What's in it

- Playing as your own cat: talking, patrols, the Dark Forest, shunning, affairs and more
- Real cat genetics: coat color, patterns, white spotting, eyes, fur types, ear and tail traits, genetic conditions and offspring prediction
- Physical traits passed down as genes: saber teeth, manes, ear tufts and more
- A custom cat maker for your main character that can pick all of it
- A Cat Editor (turn it on in the settings) to change any cat's personality, stats, health, faith, relationships and looks
- Cat picking screens you can sort, search and filter by group
- Cats with their own faith, and flirting with your mate
- Multi clan mode (optional, picked when you make a new clan), where the other Clans have their own real cats
- Built on the newest development versions of Genemod, LifeGen and ClanGen

See [changelog.txt](changelog.txt) for what's new.

## Planned features

Buttergen is just getting started. These are on the way, roughly in this order (plans can change):

- **Affairs:** a reworked affairs system
- **Code and Borders:** living by (or breaking) the warrior code, and murder of other Clans' cats, with honor loss, angry neighbors, exile and even war
- **Skills and mentors:** seven skills that level up with experience and change how patrols and your choices go, with mentors who teach them
- **Genes matter:** a cat's genes affect their skills, like camouflage in their biome, coat thickness in the cold, and size and build
- **Territory:** prey, weather and hazards, and how well your Clan is holding its land
- **Better Honor system:** witnesses, blackmail, rumors, and redemption
- **Faith and the afterlife:** dreams, omens, crises of faith, and StarClan and the Dark Forest trying to recruit cats
- **Diplomacy and war** between the Clans
- **Healers:** deeper medicine cat gameplay
- **Legacy:** what your cat leaves behind

## Credits

Buttergen is built on other people's work. Thank you to all of them!

### Mods

- **Inheritable Physical Traits** by Snow: [Discord channel](https://ptb.discord.com/channels/1003759225522110524/1258224367314272277)
- **Various Names**: [Discord channel](https://ptb.discord.com/channels/1003759225522110524/1294833972366545070)
- **Beetle's Eyes**: [Discord channel](https://ptb.discord.com/channels/1003759225522110524/1172013724597501983)
- **Mink's Torties**: [Discord channel](https://ptb.discord.com/channels/1003759225522110524/1204352226181644360)
- **Simple Dark Patches**: [Discord channel](https://ptb.discord.com/channels/1003759225522110524/1206744379688091758)
- **More Info** by coffee: [Discord channel](https://ptb.discord.com/channels/1003759225522110524/1212668667314311179)
- **Foxies Traits Galore**: [Discord channel](https://ptb.discord.com/channels/1003759225522110524/1216180193706901524)
- **Theo's Patrols**: [Discord channel](https://ptb.discord.com/channels/1003759225522110524/1290539309694193755)
- **Meaner ClanGen**: [Discord channel](https://ptb.discord.com/channels/1003759225522110524/1286100028653436940)

### Art

- Paralyzed cat sprites by **clay-and-teeth**

### LifeGen
Made by the **LifeGen team**: playing as your own cat.
- GitHub: [sedgestripe/clangen](https://github.com/sedgestripe/clangen)
- Full list of everyone who worked on it: [LifeGen credits](https://docs.google.com/document/d/1XCm5Eo-y5VA6W9quDMbF3VNyKL7S8_9Tl4c2buuiA8g/edit?usp=sharing)

### Genemod (Genetics mod)
Made by **Chinch-Bug** and contributors. Genemod gives every cat real, inheritable genes.
- GitHub: [Chinch-Bug/clangen-genemod](https://github.com/Chinch-Bug/clangen-genemod)

### LifeGen Genetics
Buttergen started from **LifeGen Genetics** by Tropicaluwu, which brought LifeGen and Genemod together.
- GitHub: [Tropicaluwu/Lifegen-Genetics-dev](https://github.com/Tropicaluwu/Lifegen-Genetics-dev)

### ClanGen
The game everything is built on. Original creator **just-some-cat**, fan edit by **SableSteel** and the ClanGen team.
- GitHub: [ClanGenOfficial/clangen](https://github.com/ClanGenOfficial/clangen)
- Itch.io: [sablesteel.itch.io/clan-gen-fan-edit](https://sablesteel.itch.io/clan-gen-fan-edit)

### Dev testers
Thank you to the Buttergen dev testers for playing early versions and finding bugs!

Buttergen is an unofficial fan project. **Please don't take bug reports from it to the LifeGen, Genemod or ClanGen teams.** They didn't make this version and can't help with it.

## License

Code is under the Mozilla Public License 2.0, and the sprites and art are under CC BY-NC 4.0, the same as ClanGen and the mods Buttergen is built on. That means you can share and change them, but not sell them, and you have to credit the artists. See [LICENSE.md](LICENSE.md).
