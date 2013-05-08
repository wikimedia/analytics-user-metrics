import MySQLdb
import xml.etree.cElementTree as ET
from xml.etree.ElementTree import tostring


namespace = '{http://www.mediawiki.org/xml/export-0.8/}'

params = {'id': 'log_id',
          'type': 'log_type',
          'action': 'log_action',
          'timestamp': 'log_timestamp',
          'contributor': 'log_contributor',
          'namespace': 'log_namespace',
          'logtitle': 'log_title',
          'params':'log_params',
          }

class Db(object):
  def __init__(self):
    self.host = '127.0.0.1'
    self.port = 3306
    self.username = ''
    self.password = ''
    self.conn = MySQLdb.connect(host=self.host, user=self.username, passwd=self.password, db="wiki", use_unicode=True)
    self.conn.set_character_set('utf8')
    self.cursor = self.conn.cursor()
    self.cursor.execute('SET NAMES utf8;')
    self.cursor.execute('SET CHARACTER SET utf8;')
    self.cursor.execute('SET character_set_connection=utf8;')

class LogItem(object):
  def __init__(self, rawLogItem):
    self.rawLogItem = rawLogItem
    self.data = self.parseLogItem()
    if self.data.get('log_params') == None:
     self.data['log_params'] = ''

  def parseLogItem(self):
    data = {}
    for elem in self.rawLogItem.iter():
      if elem.tag != '%slogitem' % namespace:
        if elem.tag.find('contributor') > -1:
          datat = self.extract_user(data, elem)
        else:
          key = elem.tag.replace(namespace,'')
          key = params.get(key)
          if key != None:
            data[key] = elem.text
    return data

  def extract_user(self, data, elem):
    data['log_user'] = elem.find('%sid' % namespace).text
    data['log_user_text'] = elem.find('%susername' % namespace).text

def main():
  entries = []
  ids = []
  source = open('/home/vagrant/test2wiki-20130430-pages-logging.xml', 'r')
  for event, elem in ET.iterparse(source, events=("start", "end")):
    if event == 'end':
      if elem.tag.find('logitem') > -1:
        tostring(elem)
        entry = LogItem(elem)
        if entry.data.get('log_id') not in ids:
          entries.append(entry)
          ids.append(entry.data.get('log_id'))
  source.close()
  database = Db()

  fields = ','.join(entries[0].data.keys())
  keys = ','.join(['%s' for i in xrange(8)])
  sql = 'INSERT INTO logging (%s) VALUES (%s)' %  (fields, keys)
  values = [tuple(entry.data.values()) for entry in entries]
  db = Db()
  db.cursor.executemany(sql, values)
  db.conn.commit()
  db.cursor.close()
  db.conn.close()

if __name__ == '__main__':
  main()
