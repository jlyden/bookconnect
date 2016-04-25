# Project: Book Connect  - jennifer lyden

## Synopsis
- Book Connect is a social media web app which facilitates connections between private book sellers and interested buyers, who subsequently meet locally (face-to-face) to exchange book and payment.
- Program sets up database of Users and Books, and includes a python module to run the app.
- Developed from scratch

## Required Libraries and Dependencies
* You will need Python v2 or higher, SQLAlchemy, Flask, Flask-Mail, and Oauth2client to run this project.
* You will also need the following Python modules: httplib2 and requests.

## Installation

### To Install
Download the zip file and extract the "bookconnect" folder inside.

### To Setup the Database
From the command line, run `python bc_db_setup.py` to create a database containing two tables: Users and Books.

### To Run
From the command line, run `python bc_handler.py` Now BookConnect is up and running. You can visit it locally at http://localhost:5000.

## Adaptation Notes
BookConnect's primary search utilizes course numbers, which vary from school to school. The format for which BookConnect is currently optimized is XXX-###, i.e. three letters, followed by a dash, followed by 3 numbers. If your school's course numbering system is different, you will need make adjustments in the following locations:
* in bc_handler.py: courseParser function, starting at line 451 
* in templates folder, adjust the instructions for entering course number in following files: bookNew.html, connect.html, inventoryNo.html, inventoryYes.html, recentsNo.html, recentsYes.html, resultsNo.html, resultsYes.html, search.html
