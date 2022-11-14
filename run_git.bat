@cls
@echo off
scons --clean
git init
git add --all
git commit -m "Versión 0.1"
git remote add origin https://github.com/hxebolax/zKeybase-generador-de-enlaces.git
git push -u origin master
git tag 0.3
git push --tags
pause