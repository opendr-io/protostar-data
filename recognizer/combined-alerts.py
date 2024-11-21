import subprocess
from io import StringIO
from datetime import datetime
from pathlib import Path

def main():
  elastic_directory = Path("elastic")
  suricata_directory = Path('suricata')
  elastic_directory.mkdir(parents=True, exist_ok=True)
  suricata_directory.mkdir(parents=True, exist_ok=True)
  
  decision = input("Which module would you like to run (Enter Number):\n1. Elastic\n2. Suricata\n3. Both\nEnter Module: ")
  if(decision == "3"):
    subprocess.run(['python', 'suricata.py'])
    subprocess.run(['python', 'elastic.py'])
  elif(decision == "2"):
    subprocess.run(['python', 'suricata.py'])
  elif(decision == "1"):
    subprocess.run(['python', 'elastic.py'])
  else:
    print("Sorry that's an invalid option")
main()