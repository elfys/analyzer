## Installation

1. Run the following command in PowerShell to install analyzer.exe
   ```powershell
   Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/elfys/analyzer/main/install.ps1" -OutFile "./install-analyzer.ps1"; &"./install-analyzer.ps1"; & rm "install-analyzer.ps1"
   ```
2. Restart PowerShell and run `analyzer.exe`


## Development

1. Install pyenv:
    - [Instructions](https://pyenv-win.github.io/pyenv-win/#installation) for windows
    - [Instructions](https://github.com/pyenv/pyenv#installation) for Linux and MacOS
2. Install PipEnv python module
   `pip install --user pipenv`
3. Clone this repository
   `git clone https://github.com/elfys/analyzer.git`
4. Navigate to the project directory
   `cd analyzer`
5. Install python dependencies
   `python -m pipenv install --dev`
     <details><summary>Expected output (on MacOS)</summary>
     <pre>
     Creating a virtualenv for this project...
     Pipfile: ~/projects/analyzer/Pipfile
     Using ~/.pyenv/versions/3.10.1/bin/python3 (3.10.1) to create virtualenv...
     ⠦ Creating virtual environment...created virtual environment
     ✔ Successfully created virtual environment! 
     Virtualenv location: ~/.local/share/virtualenvs/analyzer_sql-jP6szl67
     Installing dependencies from Pipfile.lock (f950b0)...
     🐍   ▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉ 13/13 — 00:00:06
     Ignoring pywin32: markers 'sys_platform == "win32"' don't match your environment
     To activate this project's virtualenv, run pipenv shell.
     Alternatively, run a command inside the virtualenv with pipenv run.
        </pre></details>
6. Activating the new virtual environment
   `python -m pipenv shell`

### Useful commands

- `pylint $(git diff --name-only  | grep '\.py$')` - run pylint linter on changed files
- `black --line-length 100 $(git diff --name-only  | grep '\.py$')` - run black formatter on changed files
- `flake8 .` - run flake8 linter
- `python -m analyzer db dump -l 100` - create a small dump
- `gzip -d dump_20230202_183945.sql.gz` - unarchive dump
- `docker compose up` - start database

## Usage

Running the installed program: `analyzer.exe --help`
Similarly, you can run the program from the source code: `python -m analyzer --help`

```
   █████╗  ███╗   ██╗  █████╗  ██╗   ██╗   ██╗ ███████╗ ███████╗ ██████╗ 
  ██╔══██╗ ████╗  ██║ ██╔══██╗ ██║   ╚██╗ ██╔╝ ╚══███╔╝ ██╔════╝ ██╔══██╗ 
  ███████║ ██╔██╗ ██║ ███████║ ██║    ╚████╔╝    ███╔╝  █████╗   ██████╔╝ 
  ██╔══██║ ██║╚██╗██║ ██╔══██║ ██║     ╚██╔╝    ███╔╝   ██╔══╝   ██╔══██╗ 
  ██║  ██║ ██║ ╚████║ ██║  ██║ ███████╗ ██║    ███████╗ ███████╗ ██║  ██║ 
  ╚═╝  ╚═╝ ╚═╝  ╚═══╝ ╚═╝  ╚═╝ ╚══════╝ ╚═╝    ╚══════╝ ╚══════╝ ╚═╝  ╚═╝

Options:
  --log-level [DEBUG|INFO|WARNING|ERROR]
                                  Log level.  [default: INFO]
  --db-url TEXT                   Database URL.
  --help                          Show this message and exit.

Commands:
  compare-wafers  Compare wafers
  db              Set of commands to manage related database
  parse           Parse files with measurements and save to database
  show            Show data from database
  summary         Group of command to analyze and summaryze the data
```
