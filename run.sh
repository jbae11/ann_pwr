clear
rm -rf build
rm cyclus.sqlite
python setup.py install
cyclus test.xml