@cls
@echo off
echo Creando complemento...
scons --clean
scons
scons pot
zKeybase-0.3.nvda-addon