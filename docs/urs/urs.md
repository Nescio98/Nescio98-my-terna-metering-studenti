### User Requirements Specification Document
##### DIBRIS – Università di Genova. Scuola Politecnica, Software Engineering Course 80154


**VERSION : 1.0**

**Authors**  
Simone Palladino  
Edoardo Bianco

**REVISION HISTORY**

| Version    | Date        | Authors      | Notes        |
| ----------- | ----------- | ----------- | ----------- |
| 1.0 | 14-01-2023 | Simone Palladino, Edoardo Bianco | First Draft |

# Table of Contents

1. [Introduzione](#p1)
	1. [Document Scope](#sp1.1)
	2. [Definitios and Acronym](#sp1.2) 
	3. [References](#sp1.3)
2. [System Description](#p2)
	1. [Context and Motivation](#sp2.1)
	2. [Project Objectives](#sp2.2)
3. [Requirement](#p3)
 	1. [Stakeholders](#sp3.1)
 	2. [Functional Requirements](#sp3.2)
 	3. [Non-Functional Requirements](#sp3.3)
  
  

<a name="p1"></a>

## 1. Introduzione
Il documento presente descrive i requisiti funzionali e non-funzionali di un sistema che vuole poter integrare un codice già esistente, ma non funzionante, per prendere una grossa quantità di dati dal sito di Terna, un operatore di reti per l'energia elettrica in Italia, e salvarli in maniera ordinata nel database dell'azienda.
<a name="sp1.1"></a>

### 1.1 Document Scope
Il documento descrive le funzionalità del sistema, spiegando i servizi forniti e i vincoli sotto i quali deve operare.
<a name="sp1.2"></a>

### 1.2 Definitios and Acronym


| Acronym				| Definition | 
| ------------------------------------- | ----------- | 
|AWS|Amazon web services|
|S3|Amazon Simple Storage Service|


<a name="sp1.3"></a>

### 1.3 References
ancora nessun documento ci è stato consegnato.

<a name="p2"></a>

## 2. System Description
<a name="sp2.15"></a>

### 2.1 Context and Motivation
EGO è leader in Italia nella valorizzazione dell’energia prodotta da fonti rinnovabili e nell'efficienza energetica, acquista l’energia prodotta da circa 1500 impianti di produzione di energia, per poi venderla sul mercato elettrico nazionale. Al fine di ottimizzare la vendita sul mercato dell'energia prodotta dagli impianti dispacciati da EGO, è necessario conoscere la produzione di energia e altre grandezze fisiche e operative degli impianti in tempo reale. L'applicativo vuole facilitare la gestione e il salvataggio dei dati forniti da Terna (spieghiamo qui cosa c'è in quei dati), al fine di poter calcolare i conguagli fino a cinque anni indietro.
<a name="sp2.2"></a>

### 2.2 Project Obectives 
L'applicativo vuole poter accedere ad un grosso database privo di api, e attraverso un web scraper scaricare automaticamente i dati utili per il calcolo dei conguagli. Le tipologie di dati e il range temporale su cui cercare i dati devono poter essere inseriti manualmente. Dovremo poter accedere ad un database relazionale contente i metadati necessari per effettuare la ricerca nel sito, e successivamente parallelizzare la fase di download dei file per poi salvarli su S3, aggiornando i dati che sono stati modificati e lasciando invariati i dati che non sono stati modificati.
<a name="p3"></a>

## 3. Requirements

| Priorità | Significato | 
| --------------- | ----------- | 
| M | **Mandatory:**   |
| D | **Desiderable:** |
| O | **Optional:**    |
| E | **future Enhancement:** |

<a name="sp3.1"></a>
### 3.1 Stakeholders
Matteo Fattore - Chief Information Officer
Fabio Garagiola - Software Architect
Stefano Balboni - Responsabile Database
EGO Energy S.R.L
EGO Data S.R.L
Terna S.P.A

<a name="sp3.2"></a>
### 3.2 Functional Requirements 

| ID | Descrizione | Priorità |
| --------------- | ----------- | ---------- | 
| f1 | Il sistema dovrebbe essere in grado di scaricare dati da un sito web senza api |M|
| f2 | Il sistema dovrebbe poter permettere la specifica da parte dell'utente riguardo al range temporale dei dati da scaricare  |D|
| f3 | Il sistema dovrebbe accedere a dati fino a 5 anni nel passato |M|
| f4 | Il sistema dovrebbe gestire problematiche di time out causate dal sito di Terna |M|
| f5 | Il sistema di lettura all'interno del sito di Terna dovrebbe poter essere parallelizzabile |D|
| f6 | Il sistema dopo aver scaricato i dati dovrebbe salovarli su s3 con una struttura ancora da esplicitare...(sospeso) |D|
| f7 | Il sistema dovrebbe inviare una notifica via mail specificando quali impianti sono stati aggiornati |D|
| f8 | Il sistema dovrebbe poter caricare i file su S3 in formato binario invece che come csv |O|


<a name="sp3.3"></a>
### 3.2 Non-Functional Requirements 
 
| ID | Descrizione | Priorità |
| --------------- | ----------- | ---------- | 
| nf1 | Il sistema dovrebbe terminare l'operazione di letttura e scrittura dei 5 anni di dati in meno di 12 ore |D|
| nf2 | Il sistema dovrebbe essere robusto a eventuali problematiche del sito di Terna |M|
| nf3 | Il sistema dovrebbe avere buone performance che non superino le 12 ore per risolvere la query più complessa |D|
