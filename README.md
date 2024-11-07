
Etape in realizarea proiectului
MQTT v5 server

1.	Înțelegerea noțiunilor de bază ale protocolului MQTT 
1.1.	Specificațiile protocolului MQTT: 
1.1.1.	Am început prin a citi specificațiile MQTT v5. În acest document este definit modul în care ar trebui să se comporte clienții și serverele, inclusiv structurile pachetelor, nivelurile QoS și codurile de eroare.
1.2.	Fluxul de lucru al protocolului:
1.2.1.	Am analizat fluxul de mesaje și schimburi de pachete într-o sesiune MQTT. Aceasta include: CONNECT, PUBLISH, SUBSCRIBE, DISCONNECT și pachetele de confirmare.

  	![image](https://github.com/user-attachments/assets/c0873978-94f9-4142-9562-f0d5a5f39617)
   
3.	Proiectarea arhitecturii serverului
2.1.	Arhitectura serverului se imparte în următoarele categorii:
2.1.1.	 Structura modulară: 
2.1.1.1.	Proiectarea modulelor pentru diferite aspecte ale MQTT, cum ar fi gestionarea conexiunilor, gestionarea sesiunilor, rutarea mesajelor și gestionarea subiectelor.
2.1.2.	 Concurență: 
2.1.2.1.	Planificarea modului în care vor fi gestionate conexiunile multiple. Opțiunile includ multi-threading, I/O asincrone sau utilizarea unei arhitecturi de server non-blocking. 
2.1.3.	Gestionarea sesiunilor: 
2.1.3.1.	Proiectarea unor mecanisme pentru menținerea sesiunilor clienților, în special a celor cu conexiuni persistente și cerințe QoS.
4.	Bazele programării socket
3.1.	Deoarece vor fi utilizate socket-uri in mod direct, este esențială programarea socket-urilor la nivel scăzut: 
3.1.1.	Configurarea socket-ului: 
3.1.1.1.	Un server TCP va fi configurat care ascultă pe un port, acceptă conexiuni ale clienților și face schimb de date. Sunt considerate utilizarea socket-urilor neblocante sau a unei abordări bazate pe evenimente pentru a gestiona mai mulți clienți fără a bloca o singură conexiune.
5.	Implementarea parserului și serializatorului de pachete MQTT
4.1.	MQTT se bazează pe un protocol binar, deci vor trebui analizate și construite pachete binare în conformitate cu specificațiile MQTT v5:
4.1.1.	Tipuri de pachete: 
4.1.1.1.	Vom construe funcții pentru a analiza și construi fiecare tip de pachet, cum ar fi CONNECT, CONNACK, PUBLISH, PUBACK, SUBSCRIBE și SUBACK.
4.1.2.	Proprietăți și metadate: 
4.1.2.1.	Gestionarea proprietăților MQTT v5 (de exemplu, intervalul de expirare a sesiunii, intervalul de expirare a mesajului) prin citirea și scrierea acestor câmpuri în pachete.
4.1.3.	Coduri de eroare: 
4.1.3.1.	Vom implementa codurile și condițiile de eroare MQTT v5 pentru a face serverul să fie conform cu protocolul.

![image](https://github.com/user-attachments/assets/8940a0d4-e20b-4054-b6a0-7e6fe353612e)

   
7.	Construirea funcțiilor MQTT de bază pas cu pas
5.1.	Vom implementa fiecare caracteristică de bază individual:
5.1.1.	CONNECT și CONNACK:
5.1.1.1.	Începem cu conexiunile clienților, gestionând pachetele CONNECT și răspunzând cu CONNACK.
5.1.2.	Gestionarea sesiunii: 
5.1.2.1.	Menținerea sesiunilor clienților, inclusiv a sesiunilor persistente, acolo unde este cazul. Stocarea informațiilor despre client, a subiectelor și a stărilor mesajelor pentru recuperarea sesiunii.
5.1.3.	Mecanismul Publish/Subscribe:
5.1.3.1.	Implementarea unui flux de lucru de bază PUBLISH și SUBSCRIBE pentru schimbul de mesaje între clienți.
5.2.	Niveluri QoS: Implementați diferitele niveluri QoS:
5.2.1.	QoS0: Nu este necesară confirmarea primirii pachetului.
5.2.2.	QoS1: Confirmare de primire cu un pachet PUBACK.
5.2.3.	QoS2: Implementează protocolul de handshake în patru pași pentru livrarea exact o singură dată (PUBREC, PUBREL, PUBCOMP).
5.3.	Keep Alive și Last Will:
5.3.1.	Implementarea intervalului keep-alive și gestionarea deconectărilor prin trimiterea mesajului Last Will către clienții abonați.
8.	Autentificare și securitate
6.1.	Autentificare: 
6.1.1.	Vom avea o autentificarea simplă prin nume de utilizator/parolă .
9.	Implementarea manipulării și înregistrării erorilor
7.1.	Coduri de eroare: 
7.1.1.	Implementarea codurile de eroare MQTT v5 pentru a trimite feedback clar clienților.
7.2.	Înregistrare:
7.2.1.	Vom implementa înregistrări detaliate pentru a urmări conexiunile, fluxurile de mesaje, erorile și deconectările.
10.	Resurse utilizate
8.1.	MQTT v5 Specifications: Documentația oficială MQTT v5.0 oferă detalii complete privind structura și comportamentul protocolului.
8.2.	Socket Programming Guides:
8.2.1.	C: GeeksforGeeks oferă un tutorial informativ privind programarea socket-urilor în C, acoperind atât implementările client, cât și cele server. GeeksforGeeks
8.3.	MQTT Protocol and Libraries:
8.3.1.	Mosquitto: Un broker MQTT open-source care poate servi drept referință pentru cele mai bune practici în implementarea serverului MQTT. Codul sursă este disponibil pe GitHub. Steve's Internet Guide

