@cls
@echo off
echo Creando complemento...
scons --clean
scons
scons pot
zKeybase-0.4.1.nvda-addon