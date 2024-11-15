import psycopg2
import subprocess
import time
import os
from psycopg2 import Error

class Worker:
    def __init__(self, user_name, ip_addr, slot_name) -> None:
        self.user_name = user_name
        self.ip_addr = ip_addr
        self.slot_name = slot_name

class Work:
    def __init__(self) -> None:
        self.Master = Worker("primary", "192.168.56.101", "rep101")
        self.StandBy = Worker("standby", "192.168.56.102", "rep102")

    def get_connect(self, ip_addr):
        return  psycopg2.connect(user="kronos", password="qqqqqqqq", host=ip_addr, port="5432", database="testdb")
    
    def connectToDataBase(self, ip_addr):
        try:
            connect = self.get_connect(ip_addr)
            cursor = connect.cursor()
            sql_query = 'SELECT 1;'
            cursor.execute(sql_query)
            connect.commit()
        except (Exception, Error) as error:
            print(error)

    def isAvailable(self, ip_addr):
        if os.system(f"ping -c 1 {ip_addr} > /dev/null") == 0:
            return True
        else:
            return False

    def stopDataBase(self, user_name, ip_addr):
        rc = os.system(f"ssh {user_name}@{ip_addr} '$HOME/project/bin/pg_ctl -D ~/db stop'")
        if rc != 0:
            print("Error stop DB!")
            return

    def startDataBase(self, user_name, ip_addr):
        rc = os.system(f"ssh {user_name}@{ip_addr} '~/project/bin/pg_ctl -D ~/db start'")
        if rc != 0:
            print("Error start DB!")
            return

    def dropReplicationSlot(self, ip_addr, slot_name):
        try:
            connect = self.get_connect(ip_addr)
            cursor = connect.cursor()
            cursor.execute("SELECT pg_drop_replication_slot('%s');" % slot_name)
            cursor.close()
            connect.close()
            return True
        except (Exception, Error) as error:
            return False

    def createReplicationSlot(self, user_name, ip_addr, slot_name):
        self.dropReplicationSlot(ip_addr, slot_name)

        rc = os.system(f"ssh {user_name}@{ip_addr} '~/project/bin/pg_basebackup -h {ip_addr} -p 5432 -U kronos --create-slot --slot={slot_name} --write-recovery-conf -D ~/db'")

        if rc != 0:
            print("Error replication!\n")
            return

    def rewind(self, user_name, ip_addr, ip_addr_main):
        rc = os.system(f"""ssh {user_name}@{ip_addr} '~/project/bin/pg_rewind -D ~/db --source-server="dbname=testdb user=kronos host={ip_addr_main} port=5432" -R'""")

        if rc != 0:
            print('Error rewind\n')
            return

    def createReplicatonSlotAgain(self, user_name, ip_addr, ip_addr_main, slot_name):
        cmd = ['ssh', f'{user_name}@{ip_addr}',
               f"~/project/bin/psql -h {ip_addr_main} -U kronos --dbname=testdb -c \"SELECT * FROM pg_create_physical_replication_slot('{slot_name}');\""]
        rc = subprocess.run(cmd, capture_output=True, text=True)

        if rc.returncode != 0:
            print("Error create replication slot again\n")
            return

    def main(self):
        promote = False
        while True:
            if self.isAvailable(self.Master.ip_addr):
                self.connectToDataBase(self.Master.ip_addr)
                print("connect to Main DB\n")
            elif self.isAvailable(self.StandBy.ip_addr) and not promote:
                print("Main DB is not avalible\n")
                self.connectToDataBase(self.StandBy.ip_addr)
                print("Promote Second DB...\n")
                rc = os.system(f"ssh {self.StandBy.user_name}@{self.StandBy.ip_addr} '$HOME/project/bin/pg_ctl -D $HOME/db promote'")
                if rc == 0:
                    promote = True
                    print("Promote complete!\n")
                else:
                    print("Error promote!\n")
            elif self.isAvailable(self.StandBy.ip_addr):
                self.connectToDataBase(self.StandBy.ip_addr)
                print("Connect to Second DB\n")
            else:
                print("Error connection!\n")

            if self.isAvailable(self.Master.ip_addr) and promote:
                print("Revert to Main DB\n")
                self.connectToDataBase(self.Master.ip_addr)

                try:
                    print("Stop Main DB\n")
                    self.stopDataBase(self.Master.user_name, self.Master.ip_addr)
                    print("Create Replication on Main DB\n")
                    self.rewind(self.Master.user_name, self.Master.ip_addr, self.StandBy.ip_addr)
                    self.createReplicatonSlotAgain(self.Master.user_name, self.Master.ip_addr, self.StandBy.ip_addr, self.StandBy.slot_name)
                    print("start Main DB\n")
                    self.startDataBase(self.Master.user_name, self.Master.ip_addr)
                    print("promote Main DB\n")
                    rc = os.system(f"ssh {self.Master.user_name}@{self.Master.ip_addr} '$HOME/project/bin/pg_ctl -D $HOME/db promote'")
                    if rc == 0:
                        promote = True
                        print("Promote complete!\n")
                    else:
                        print("Error promote!\n")
                    print("Stop Second DB\n")
                    self.stopDataBase(self.StandBy.user_name, self.StandBy.ip_addr)
                    print("Create Replication on Second DB\n")
                    self.rewind(self.StandBy.user_name, self.StandBy.ip_addr, self.Master.ip_addr)
                    self.createReplicatonSlotAgain(self.StandBy.user_name, self.StandBy.ip_addr, self.Master.ip_addr, self.StandBy.slot_name)
                    self.startDataBase(self.StandBy.user_name, self.StandBy.ip_addr)
                    print("Revert to Main DB complete!\n")
                    promote = False
                except (Exception, Error) as error:
                    print(error)
            
            time.sleep(2)
        
            



if __name__=="__main__":
    work = Work()
    work.main()