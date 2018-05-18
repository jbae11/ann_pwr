rm cyclus.sqlite
rm log.txt
rm -r ../build
python ../setup.py install
cyclus test.xml
cat log.txt