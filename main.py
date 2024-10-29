from datetime import datetime, timezone
from flask import Flask, Response, jsonify, request  
from flask_sqlalchemy import SQLAlchemy 
import json
import paho.mqtt.client as mqtt 

# pip install paho-mqtt flask -> conexao com os sensores

#conexao com o BANCO DE DADOS

#noma da aplicacao
app = Flask("registro")
# configura o SQLAlchemy para rastrear modificacoes
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# configura a URI de conexao com o banco de dados MySQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:senai%40134@127.0.0.1/bd_medidor'

#cria uma instancia do SQLAlchemy, passando a aplicacao Flask como parametro.
mybd = SQLAlchemy(app)

# conexao dos sensores
mqtt_dados = {}

def conexao_sensor(client, userdata, flags, rc):
    client.subscribe("projeto_integrado/SENAI134/Cienciadedados/GrupoX")

def msg_sensor(client, userdata, msg):
    global mqtt_dados
    # decodificar a mensagem recebida de bytes para string
    valor =msg.payload.decode('utf-8')
    #decodificar de string para JSON
    mqtt_dados = json.loads(valor)

    print(f"Mensagem Recebida: {mqtt_dados}")

# correlaco banco de dados com sensores
    with app.app_context():
        try:
            temperatura = mqtt_dados.get('temperature')
            pressao = mqtt_dados.get('pressure')
            altitude = mqtt_dados.get('altitude')
            umidade = mqtt_dados.get('humidity')
            co2 = mqtt_dados.get('co2')
            poeira = 0
            tempo_registro = mqtt_dados.get('timestamp')

            if tempo_registro is None:
                print("timestamp nao encontrado")
                return
            
            try:
                tempo_oficial = datetime.fromtimestamp(int(tempo_registro), tz=timezone.utc)
            
            except (ValueError, TypeError) as e:
                print(f"erro ao converter timestamp: {str(e)}")
                return
            
# criar o objeto que vai simular a tabela do banco 

            novos_dados = Registro(
                temperatura = temperatura,
                pressao = pressao,
                altitude = altitude,
                co2 = co2,
                poeira = poeira,
                tempo_registro = tempo_oficial
            )

            #adicionar novo registro ao banco

            mybd.session.add(novos_dados)
            mybd.session.commit()
            print("dados foram inseridos com sucesso no banco de dados!")

        except Exception as e:
            print(f"erro ao processar os dados do MQTT:{str(e)}")
            mybd.session.rollback()

mqtt_client = mqtt.Client()
mqtt_client.on_connect = conexao_sensor
mqtt_client.on_message = msg_sensor
mqtt_client.connect("test.mosquitto.org",1883,60)

def start_mqtt():
    mqtt_client.loop_start()

class Registro(mybd.Model):
    _tablename_ = 'tb_registro'
    id = mybd.Column(mybd.Integer, primary_key=True, autoincrement=True)
    temperatura = mybd.Column(mybd.Numeric(10,2))
    pressao = mybd.Column(mybd.Numeric(10,2))
    altitude = mybd.Column(mybd.Numeric(10,2))
    umidade = mybd.Column(mybd.Numeric(10,2))
    co2 = mybd.Column(mybd.Numeric(10,2))
    poeira = mybd.Column(mybd.Numeric(10,2))
    tempo_registro = mybd.Column(mybd.DateTime)

    # ***************** 
    # **** GET *************

    @app.route("/registro", methods=["GET"])
    def seleciona_registro():
        registro_objetos = Registro.query.all()
        registro_json = [registro.to_json() for registro in registro_objetos]
    
        return gera_resposta(200, "registro",registro_json)
    
    # ************
    def gera_resposta(status, nome_do_conteudo,conteudo, mensagem=False):
        body = {}
        body[nome_do_conteudo] = conteudo

        if mensagem:
            body["mensagem"] = mensagem
        return Response(json.dumps(body),status=status, mimetype="application/json")    



# *******************
# ******** GET - POR ID ******
    @app.route("/registro/<id>", methods=["GET"])
    def seleciona_registro_id(id):
        registro_objetos = Registro.query.filter_by(id=id).first()
        if registro_objetos:
            registro_json = registro_objetos.to_json()
            return gera_resposta(200, "registro", registro_json)
        else:
            return gera_resposta(404, "registro",{}, "registro nao encontrado")
        

# ********************
# ***** DELETE *************
 
    @app.route("/registro/<id>", methods=["DELETE"])
    def deleta_registro(id):
        registro_objetos = Registro.query.filter_by(id=id).first()

        if registro_objetos:
            try:
                mybd.session.delete(registro_objetos)
                mybd.session.commit()
                return gera_resposta(200, "registro", registro_objetos.to_json(), "deletado com sucesso!")
            except Exception as e:
                print('erro', e)
                mybd.session.rollback()
                return gera_resposta(400,"registro",{}, "erro ao deletar")
        else: 
            return gera_resposta(404,"registro",{},"registro nao encontrado")



# **************************
# *********** POST  GET - SENSORES*************
@app.route("/dados", methods=["GET"])
def bisca_dados():
    return jsonify(mqtt_dados)

def to_json(self):
    return{
        "id": self.id,
        "temperatura": float(self.temperatura),
        "pressao": float(self.pressao),
        "altitude": float(self.altitude),
        "umidade": float(self.umidade),
        "co2": float(self.co2),
        "poeira": float(self.poeira),
        "tempo_registro": self.tempo_registro.strftime('%y-%m-%d %H: %M: %S')
        if self.tempo_registro else None
    }

# ******** POST *********

@app.route("/dados", methods=["POST"])
def criar_dados():
    try:
        dados = request.get_json()

        if not dados:
            return jsonify({"error":"nenhum dado fornecido"}), 400
        
        print(f"dados recebidos: {dados}")
        temperatura = dados.get('temperatura')
        pressao = dados.get('pressao')
        altitude = dados.get('altitude')
        umidade = dados.get('umidade')
        co2 = dados.get('co2')
        poeira = dados.get('poeira')
        timestamp_unix = dados.get('tempo_registro')

        try:
            tempo_oficial = datetime.fromtimestamp(int(timestamp_unix), tz=timezone.utc)
        except Exception as e:
            print("Erro", e)
            return jsonify({"error":"Timestamp invalido"}),400
        
        # criar o objeto de registro
        novo_registro = Registro(
            temperatura = temperatura,
            pressao = pressao,
            altitude = altitude,
            umidade = umidade,
            co2 = co2,
            poeira = poeira,
            tempo_registro = tempo_oficial
        )

        mybd.session.add(novo_registro)
        print("adicionando o novo registro")

        mybd.session.commit()
        print("dados inseridos no banco de dados com sucesso!")
        
        return jsonify({"mensagem":"dados recebidos com sucesso"}), 201
    
    except Exception as e :
        print(f"erro ao processar a solicitacao", e)
        mybd.session.rollback()
        return jsonify({"erro":"falha ao processar os dados"}), 500
    


def gera_resposta(status, nome_do_conteudo, conteudo, mensagem=False):
    body = {}
    body[nome_do_conteudo] = conteudo


    if mensagem:  # verifica se a variavel 'mensagem' foi fornecida
        body['mensgem'] = mensagem

        return Response(json.dumps(body), status=status, mimetype='application/json')
    
if __name__ == '__main__':
    with app.app_context():
        mybd.create_all()

        start_mqtt()
        app.run(port=5000, host='localhost', debug=True)