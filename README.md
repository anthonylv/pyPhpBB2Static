# pyPhpBB2Static

A Python script to migrate a phpBB 3 forum into static HTML pages.


**CAUTION:** *Consider this to be pre-alpha code.* Make a backup of your phpBB database before running this tool. USE IS ENTIRELY AT YOUR OWN RISK.

First released 2015-11-29 by Anthony Lopez-Vito of Another Cup of Coffee Limited
http://anothercoffee.net

All code is released under The MIT License.
Please see LICENSE.txt.


## Installation and use

1. Module depenendies are in the requirements.txt file
1. Copy `settings-template.yml` to `settings.yml` and enter your phpBB database credentials
1. Customise the html files in `templates/`
1. Run `python phpbb2static.py`
1. Static HTML files will be placed in an `export/` directory

## Credits
MySQL queries and basic logic are based on the [phpBB2HTML script](http://www.scriptol.com/cms/phpbb2html.php). That script didn't work for me so I wrote my own version in Python.