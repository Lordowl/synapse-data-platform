# esempio d'invocazione: powershell -File "H:\570 Measurement & data Office\IrionDQ\App\Ingestion\ingestion.ps1" -anno 2025 -settimana 34 -id "2 3333" -log_key hghjghj4ghj5ghj6ghj7ghj
param (
	[string]$anno,
	[string]$settimana,
	[string]$id,
	[string]$log_key
)

$path = Split-Path -Parent $MyInvocation.MyCommand.Definition
cd $path
.venv\Scripts\Activate.ps1
python main_ingestion.py -c main_ingestion_SPK.ini --anno $anno --settimana $settimana --id $id --log_key $log_key
