# -*- coding: utf-8 -*-
# Copyright (C) 2022 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

import globalPluginHandler
import addonHandler
import globalVars
import ui
import gui
import os
import wx
import subprocess
import json
import ctypes
import ctypes.wintypes
from scriptHandler import script
from tones import beep
from threading import Thread
from ctypes.wintypes import BOOL, HWND, HANDLE, HGLOBAL, UINT, LPVOID
from ctypes import c_size_t as SIZE_T

addonHandler.initTranslation()

# Solución extraida de https://stackoverflow.com/questions/579687/how-do-i-copy-a-string-to-the-clipboard
# Me gusta más esta forma que la interna de NVDA o la de wxpython para manejar el portapapeles, es mas directa con el sistema.

OpenClipboard = ctypes.windll.user32.OpenClipboard
OpenClipboard.argtypes = HWND,
OpenClipboard.restype = BOOL
EmptyClipboard = ctypes.windll.user32.EmptyClipboard
EmptyClipboard.restype = BOOL
GetClipboardData = ctypes.windll.user32.GetClipboardData
GetClipboardData.argtypes = UINT,
GetClipboardData.restype = HANDLE
SetClipboardData = ctypes.windll.user32.SetClipboardData
SetClipboardData.argtypes = UINT, HANDLE
SetClipboardData.restype = HANDLE
CloseClipboard = ctypes.windll.user32.CloseClipboard
CloseClipboard.restype = BOOL
CF_UNICODETEXT = 13

GlobalAlloc = ctypes.windll.kernel32.GlobalAlloc
GlobalAlloc.argtypes = UINT, SIZE_T
GlobalAlloc.restype = HGLOBAL
GlobalLock = ctypes.windll.kernel32.GlobalLock
GlobalLock.argtypes = HGLOBAL,
GlobalLock.restype = LPVOID
GlobalUnlock = ctypes.windll.kernel32.GlobalUnlock
GlobalUnlock.argtypes = HGLOBAL,
GlobalSize = ctypes.windll.kernel32.GlobalSize
GlobalSize.argtypes = HGLOBAL,
GlobalSize.restype = SIZE_T

GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = 0x0040

unicode_type = type(u'')

def clean():
	# Función para borrar el portapapeles
	OpenClipboard(None)
	EmptyClipboard()
	CloseClipboard()

def get():
	# Función para obtener el contenido del portapapeles
	text = None
	OpenClipboard(None)
	handle = GetClipboardData(CF_UNICODETEXT)
	pcontents = GlobalLock(handle)
	size = GlobalSize(handle)
	if pcontents and size:
		raw_data = ctypes.create_string_buffer(size)
		ctypes.memmove(raw_data, pcontents, size)
		text = raw_data.raw.decode('utf-16le').rstrip(u'\0')
	GlobalUnlock(handle)
	CloseClipboard()
	return text

def put(text):
	# Función para pegar contenido al portapapeles
	if not isinstance(text, unicode_type):
		text = text.decode('mbcs')
	data = text.encode('utf-16le')
	OpenClipboard(None)
	EmptyClipboard()
	handle = GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data) + 2)
	pcontents = GlobalLock(handle)
	ctypes.memmove(pcontents, data, len(data))
	GlobalUnlock(handle)
	SetClipboardData(CF_UNICODETEXT, handle)
	CloseClipboard()
# Fin solución extraida de  https://stackoverflow.com/questions/579687/how-do-i-copy-a-string-to-the-clipboard

# Solución extraida de https://stackoverflow.com/questions/7985122/show-explorers-properties-dialog-for-a-file-in-windows
# Gracias a @tinitun por el .encode() para Python 3
# Obtener el dialogo de propiedades de un archivo o directorio

SEE_MASK_NOCLOSEPROCESS = 0x00000040
SEE_MASK_INVOKEIDLIST = 0x0000000C

class SHELLEXECUTEINFO(ctypes.Structure):
	_fields_ = (
		("cbSize",ctypes.wintypes.DWORD),
		("fMask",ctypes.c_ulong),
		("hwnd",ctypes.wintypes.HANDLE),
		("lpVerb",ctypes.c_char_p),
		("lpFile",ctypes.c_char_p),
		("lpParameters",ctypes.c_char_p),
		("lpDirectory",ctypes.c_char_p),
		("nShow",ctypes.c_int),
		("hInstApp",ctypes.wintypes.HINSTANCE),
		("lpIDList",ctypes.c_void_p),
		("lpClass",ctypes.c_char_p),
		("hKeyClass",ctypes.wintypes.HKEY),
		("dwHotKey",ctypes.wintypes.DWORD),
		("hIconOrMonitor",ctypes.wintypes.HANDLE),
		("hProcess",ctypes.wintypes.HANDLE),
	)

def getAccionMenuContextual(propiedad, ruta):
	ShellExecuteEx = ctypes.windll.shell32.ShellExecuteEx
	ShellExecuteEx.restype = ctypes.wintypes.BOOL

	sei = SHELLEXECUTEINFO()
	sei.cbSize = ctypes.sizeof(sei)
	sei.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_INVOKEIDLIST
	sei.lpVerb = propiedad.encode()
	sei.lpFile = ruta.encode()
	sei.nShow = 1
	ShellExecuteEx(ctypes.byref(sei))
# Fin solución extraida de https://stackoverflow.com/questions/7985122/show-explorers-properties-dialog-for-a-file-in-windows

class Result:
 pass

def comandoRun(comando):
	result = Result()
	si = subprocess.STARTUPINFO()
	si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
	p = subprocess.Popen(comando, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf8", startupinfo=si)
	(stdout, stderr) = p.communicate()
	result.exit_code = p.returncode
	result.stdout = stdout
	result.stderr = stderr
	result.command = comando
	if p.returncode != 0:
		return [False, False]
	else:
		return [True, result.stdout]

def getList(lista, ruta):
	directorios = []
	ficheros = []
	for i in sorted(lista, key=str.casefold):
		if os.path.isdir(os.path.join(ruta, i)): # Directorio
			directorios.append("{} (D)".format(i))
		else: # Fichero
			ficheros.append("{} (F)".format(i))
	return directorios + ficheros

def disableInSecureMode(decoratedCls):
	if globalVars.appArgs.secure:
		return globalPluginHandler.GlobalPlugin
	return decoratedCls

@disableInSecureMode
class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self):
		super(GlobalPlugin, self).__init__()

		self.IS_WINON = False

	@script(gesture=None, description= _("Abrir la ventana de zKeybase para generar enlaces"), category= "zKeybase")
	def script_Run(self, gesture):
		if not self.IS_WINON:
			HiloComplemento(self, 1).start()
		else:
			ui.message("ya hay una instancia de zKeybase abierta")

class VentanaPrincipal(wx.Dialog):
	def _calculatePosition(self, width, height):
		w = wx.SystemSettings.GetMetric(wx.SYS_SCREEN_X)
		h = wx.SystemSettings.GetMetric(wx.SYS_SCREEN_Y)
		# Centre of the screen
		x = w / 2
		y = h / 2
		# Minus application offset
		x -= (width / 2)
		y -= (height / 2)
		return (x, y)

	def __init__(self, parent, frameAddon, usuario, root):

		WIDTH = 1200
		HEIGHT = 850
		pos = self._calculatePosition(WIDTH, HEIGHT)

		super(VentanaPrincipal, self).__init__(parent, -1, pos = pos, size = (WIDTH, HEIGHT))

		self.SetTitle(_("{} {}".format(addonHandler.Addon(os.path.join(globalVars.appArgs.configPath, "addons", "zKeybase")).name, addonHandler.Addon(os.path.join(globalVars.appArgs.configPath, "addons", "zKeybase")).version)))

		self.frame = frameAddon
		self.root = root
		self.usuario = usuario
		self.ruta = [self.root]
		self.posicion = [0]
		self.baseDirectorio = "https://keybase.pub/{}/{}"
		self.baseFichero = "https://{}.keybase.pub/{}?dl=1"
		self.frame.IS_WINON = True

		self.panel_1 = wx.Panel(self, wx.ID_ANY)

		sizer_1 = wx.BoxSizer(wx.VERTICAL)

		label_1 = wx.StaticText(self.panel_1, wx.ID_ANY, _("&Directorios y ficheros en Keybase:"))
		sizer_1.Add(label_1, 0, wx.EXPAND, 0)

		self.listbox_ficheros = wx.ListBox(self.panel_1, 200)
		sizer_1.Add(self.listbox_ficheros, 1, wx.ALL | wx.EXPAND, 0)

		self.panel_1.SetSizer(sizer_1)

		self.Layout()
		self.Centre()

		self.cargaEventos()
		self.cargaDatos()

	def cargaEventos(self):
		self.listbox_ficheros.Bind(wx.EVT_KEY_UP, self.onListBox)
		self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyEvent)
		self.Bind(wx.EVT_CLOSE, self.onSalir)

	def cargaDatos(self, nuevo=False):
		self.listbox_ficheros.Clear()
		if len(self.ruta) == 1: # directorio principal
			temporal = getList(os.listdir(self.ruta[0]), self.ruta[0])
			if not len(temporal):
				self.listbox_ficheros.Append(_("Sin ficheros"))
			else:
				self.listbox_ficheros.Append(temporal)
		else:
			temporal = getList(os.listdir(self.ruta[-1]), self.ruta[-1])
			if not len(temporal):
				self.listbox_ficheros.Append(_("Sin ficheros"))
			else:
				self.listbox_ficheros.Append(temporal)

		if nuevo:
			self.listbox_ficheros.SetSelection(self.posicion[-1])
		else:
			self.listbox_ficheros.SetSelection(0)

		self.listbox_ficheros.SetFocus()

	def onListBox(self, event):
		obj = event.GetEventObject()
		texto = obj.GetString(obj.GetSelection())

		if texto == _("Sin ficheros"):
			if len(self.ruta) == 1:
				return

		if event.GetKeyCode() == wx.WXK_RETURN:
			if texto[-4:]  == " (D)":
				self.ruta.append(os.path.join(self.ruta[-1], texto[:-4]))
				self.posicion.append(obj.GetSelection())
				self.cargaDatos()
			else:
				event.Skip()

		elif event.GetKeyCode() == wx.WXK_BACK:
			if texto[-4:]  == " (D)":
				if len(self.ruta) == 1:
					beep(200,150)
					return
				else:
					del self.ruta[-1]
					self.cargaDatos(True)
					del self.posicion[-1]
			else:
				if len(self.ruta) == 1:
					beep(200,150)
					return
				else:
					del self.ruta[-1]
					self.cargaDatos(True)
					del self.posicion[-1]

		elif event.GetKeyCode() == wx.WXK_F1: # Manual del complemento
			wx.LaunchDefaultBrowser('file://' + addonHandler.Addon(os.path.join(globalVars.appArgs.configPath, "addons", "zKeybase")).getDocFilePath(), flags=0)

		elif event.GetKeyCode() == wx.WXK_F2: # Generar enlace
			if texto == _("Sin ficheros"):
				return

			listaFichero = os.path.join(self.ruta[-1], texto[:-4]).split(os.sep)
			if texto[-4:]  == " (D)":
				put(self.baseDirectorio.format(self.usuario, '/'.join(listaFichero[3:]).replace(" ", "%20")))
				ui.message(_("Se a copiado la URL para el directorio de Keybase al portapapeles."))
			else:
				put(self.baseFichero.format(self.usuario, '/'.join(listaFichero[3:]).replace(" ", "%20")))
				ui.message(_("Se a copiado la URL para el archivo de Keybase al portapapeles."))

		elif event.GetKeyCode() == wx.WXK_F3: # Propiedades
			if texto == _("Sin ficheros"):
				return
			getAccionMenuContextual("properties", os.path.join(self.ruta[-1], texto[:-4]))

		elif event.GetKeyCode() == wx.WXK_F5: # Refrescar archivos y directorios
			del self.ruta[:]
			del self.posicion[:]
			self.ruta = [self.root]
			self.posicion = [0]
			self.cargaDatos()

	def OnKeyEvent(self, event):
		if event.GetUnicodeKey() == wx.WXK_ESCAPE:
			self.onSalir(None)
		else:
			event.Skip()

	def onSalir(self, event):
		self.frame.IS_WINON = False
		self.Destroy()
		gui.mainFrame.postPopup()

class HiloComplemento(Thread):
	def __init__(self, frame, opcion):
		super(HiloComplemento, self).__init__()

		self.frame = frame
		self.opcion = opcion
		self.daemon = True

	def run(self):
		def windowsApp():
			p = comandoRun(["keybase.exe", "config", "get"])
			if p[0]:
				diccionario = json.loads(p[1])
				usuario = diccionario.get("current_user")
				unidad = diccionario.get("mountdir")
				root = os.path.join(unidad, "\public", usuario)
				self._main = VentanaPrincipal(gui.mainFrame, self.frame, usuario, root)
				gui.mainFrame.prePopup()
				self._main.Show()
			else:
				msg = \
_("""No se encontró la unidad virtual de Keybase.

Asegúrese que el servicio de Keybase esta ejecutándose y tiene configurada la opción de montar la unidad virtual.""")
				ui.message(msg)

		if self.opcion == 1:
			wx.CallAfter(windowsApp)


