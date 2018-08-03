How to install:
1) Extract the contents of the zip file to a local directory.
2) Install Python 3.6 or later to your system. Choose the option on installation to add Python to your computer's Path
3) Open command prompt, navigate to the folder that you extracted the files into previously (using cd "folderpath")
	a) Make sure you're in folder that has the .py files
4) At this location, type in "pip install pipenv" to install the pipenv python package
5) Once this is finished installing, type "pipenv install ." This will install all of the required dependencies for the software

Using the software:
1) To launch the virtual environment that has been created in the last step, type "pipenv shell". This should activate the new environment, which you will see as ("environment name") in front of the command prompt >
	a) You must launch this environment any time you run the software. Just navigate to the program's directory 	in command prompt and type "pipenv shell" again 
2) When your environment is activated, type "python gui.py" and press enter. This will bring up the software GUI. (This can sometimes take several seconds)
3) From the GUI, select the top-level directory where your data is stored. This means if you have several different tests in a parent directory, you can navigate to that parent directory and select it as the folder.
4) Choose which plots you want to output (in the checkboxes).
5) Hit the run button.

Notes:
1) Logging does not occur in real time in the GUI. I spent way too long trying to make it work and eventually gave up. If you think that the program is hanging, look at your command prompt window and it should have data being output.

2) When saving your results, structure your data as shown below. This structure is useful because you can choose the "project_folder" level directory and the software will find all relevant .csv files in any subdirectories of that folder.

|--project_folder
|	|--Chassis1
|	|	|--25C
|	|	|	|--Writes
|	|	|	|	|--SMART_chassis1_25c_writes.csv
|	|	|	|	|--THERMAL_chassis1_25c_writes.csv
|	|	|	|	|--12v_chass1_25c_writes.csv
|	|	|	|	|--SMART_chassis1_25c_writes.csv
|	|	|	|--Reads
|	|	|	|	|--SMART_chassis1_25c_reads.csv
|	|	|	|	|--THERMAL_chassis1_25c_reads.csv
|	|	|	|	|--12v_chass1_25c_reads.csv
|	|	|	|	|--SMART_chassis1_25c_reads.csv
|	|--Chassis2
|	|	|--...

3) You will want to name your data as shown in this example:
Data type	:	Name
SMART data	:	SMART_xx_xx.csv
Thermal data	:	THERMAL_xx_xx.csv
Power data	:	3p3V_xx_xx.csv, 12V_xx_xx.csv