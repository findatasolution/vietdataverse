Attribute VB_Name = "RefreshData"
'==============================================================================
' Viet Dataverse — cap nhat du lieu tu API vao workbook
'
' Gan macro RefreshData cho nut CAP NHAT DU LIEU tren sheet "Bat dau".
'
' Nguyen tac thiet ke:
'   * Danh sach bo du lieu nam o sheet "Cau hinh", KHONG nam trong macro.
'     Them mot bo du lieu = them mot dong trong sheet do. Macro nay khong bao
'     gio phai sua lai, nen vbaProject.bin khong bao gio phai sinh lai.
'   * Doc CSV chu khong phai JSON. VBA khong co bo phan tich JSON, va moi cach
'     lach (ScriptControl) chi chay 32-bit. API da co format=csv cho ca 9 bo.
'   * API key doc tu o co ten API_KEY, khong luu trong macro — chia se file
'     khong lo key, doi khach hang chi la go lai mot o.
'   * Quyen truy cap do MAY CHU quyet dinh, macro chi bao lai: 401 = key sai
'     hoac het han, 429 = het luot goi trong thang. Macro khong tu phan xu,
'     nen khong the mau thuan voi API.
'
' Ghi chu ve tieng Viet: file .bas luu dang ANSI nen phan chu o day khong dau,
' con moi thong bao hien ra cho nguoi dung deu dung tieng Viet co dau (chung
' duoc ghep bang ChrW de khong phu thuoc bang ma cua trinh soan thao).
'==============================================================================
Option Explicit

Private Const CFG_SHEET As String = "C" & ChrW(7845) & "u h" & ChrW(236) & "nh"
Private Const START_SHEET As String = "B" & ChrW(7855) & "t " & ChrW(273) & ChrW(7847) & "u"

'--- Tra ve noi dung mot URL, hoac chuoi rong neu loi. Ma HTTP tra qua statusOut
Private Function HttpGet(ByVal url As String, ByRef statusOut As Long) As String
    Dim http As Object
    On Error GoTo Failed
    ' MSXML2.XMLHTTP chi co tren Windows. Excel cho Mac se roi vao nhanh Failed
    ' va bao loi ro rang thay vi treo.
    Set http = CreateObject("MSXML2.XMLHTTP")
    http.Open "GET", url, False
    http.setRequestHeader "Accept", "text/csv"
    http.send
    statusOut = http.Status
    HttpGet = http.responseText
    Exit Function
Failed:
    statusOut = -1
    HttpGet = ""
End Function

'--- Ghi noi dung CSV vao sheet, bat dau tu dong 4 (dong 1-2 la ghi chu nguon)
Private Sub WriteCsv(ByVal ws As Worksheet, ByVal csvText As String)
    Dim lines() As String, cells() As String
    Dim r As Long, c As Long, lastRow As Long
    Dim value As String

    ' Xoa du lieu cu nhung giu 2 dong ghi chu dau sheet.
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    If lastRow >= 4 Then ws.Range("A4:Z" & lastRow).ClearContents

    csvText = Replace(csvText, vbCrLf, vbLf)
    csvText = Replace(csvText, vbCr, vbLf)
    lines = Split(csvText, vbLf)

    For r = 0 To UBound(lines)
        If Len(Trim$(lines(r))) > 0 Then
            cells = Split(lines(r), ",")
            For c = 0 To UBound(cells)
                value = cells(c)
                If IsNumeric(value) And Len(value) > 0 Then
                    ws.Cells(4 + r, 1 + c).value = CDbl(value)
                Else
                    ws.Cells(4 + r, 1 + c).value = value
                End If
            Next c
        End If
    Next r

    ws.Range("A4:Z4").Font.Bold = True
End Sub

'--- Macro gan vao nut
Public Sub RefreshData()
    Dim cfg As Worksheet, ws As Worksheet
    Dim apiKey As String, base As String
    Dim sheetName As String, path As String, query As String
    Dim url As String, body As String
    Dim status As Long, r As Long
    Dim okCount As Long, failCount As Long
    Dim firstError As String

    apiKey = Trim$(CStr(Application.Names("API_KEY").RefersToRange.value))
    If Len(apiKey) = 0 Then
        Application.Names("STATUS").RefersToRange.value = _
            ChrW(178) & ChrW(185) & " " & VietMsg("noKey")
        MsgBox VietMsg("noKey"), vbExclamation, "Viet Dataverse"
        Exit Sub
    End If

    base = "https://api.vietdataverse.online"
    Set cfg = ThisWorkbook.Worksheets(CFG_SHEET)

    Application.ScreenUpdating = False
    r = 2
    Do While Len(Trim$(CStr(cfg.Cells(r, 1).value))) > 0
        sheetName = CStr(cfg.Cells(r, 1).value)
        path = CStr(cfg.Cells(r, 2).value)
        query = CStr(cfg.Cells(r, 3).value)

        url = base & "/" & path & "?"
        If Len(query) > 0 Then url = url & query & "&"
        url = url & "format=csv&api_key=" & apiKey

        Application.StatusBar = "Viet Dataverse: " & sheetName & ChrW(8230)
        body = HttpGet(url, status)

        If status = 200 And Len(body) > 0 And Left$(body, 1) <> "{" Then
            On Error Resume Next
            Set ws = ThisWorkbook.Worksheets(sheetName)
            On Error GoTo 0
            If Not ws Is Nothing Then
                WriteCsv ws, body
                okCount = okCount + 1
            End If
            Set ws = Nothing
        Else
            failCount = failCount + 1
            If Len(firstError) = 0 Then firstError = ErrorText(status, sheetName)
        End If

        r = r + 1
    Loop
    Application.ScreenUpdating = True
    Application.StatusBar = False

    Dim summary As String
    summary = Format$(Now, "dd/mm/yyyy hh:nn") & " " & ChrW(183) & " " & _
              okCount & "/" & (okCount + failCount) & " " & VietMsg("done")
    If failCount > 0 Then summary = summary & " " & ChrW(183) & " " & firstError
    Application.Names("STATUS").RefersToRange.value = summary

    If failCount > 0 Then
        MsgBox firstError, vbExclamation, "Viet Dataverse"
    Else
        MsgBox VietMsg("allOk"), vbInformation, "Viet Dataverse"
    End If
End Sub

'--- Thong bao loi theo ma HTTP, noi thang bang tieng Viet
Private Function ErrorText(ByVal status As Long, ByVal sheetName As String) As String
    Select Case status
        Case 401
            ErrorText = VietMsg("e401")
        Case 403
            ErrorText = VietMsg("e403")
        Case 429
            ErrorText = VietMsg("e429")
        Case -1
            ErrorText = VietMsg("eNet")
        Case Else
            ErrorText = VietMsg("eOther") & " (" & sheetName & ", HTTP " & status & ")"
    End Select
End Function

'--- Chuoi tieng Viet co dau, ghep bang ChrW de khong phu thuoc bang ma file
Private Function VietMsg(ByVal keyName As String) As String
    Select Case keyName
        Case "noKey"
            VietMsg = "Ch" & ChrW(432) & "a nh" & ChrW(7853) & "p API key. D" & ChrW(225) & _
                      "n key v" & ChrW(224) & "o " & ChrW(244) & " m" & ChrW(224) & "u v" & _
                      ChrW(224) & "ng " & ChrW(7903) & " sheet B" & ChrW(7855) & "t " & _
                      ChrW(273) & ChrW(7847) & "u."
        Case "done"
            VietMsg = "b" & ChrW(7897) & " d" & ChrW(7919) & " li" & ChrW(7879) & "u"
        Case "allOk"
            VietMsg = "" & ChrW(272) & ChrW(227) & " c" & ChrW(7853) & "p nh" & ChrW(7853) & _
                      "t xong t" & ChrW(7845) & "t c" & ChrW(7843) & " c" & ChrW(225) & "c sheet."
        Case "e401"
            VietMsg = "API key kh" & ChrW(244) & "ng h" & ChrW(7907) & "p l" & ChrW(7879) & _
                      ", " & ChrW(273) & ChrW(227) & " b" & ChrW(7883) & " thu h" & ChrW(7891) & _
                      "i ho" & ChrW(7863) & "c g" & ChrW(243) & "i " & ChrW(273) & ChrW(227) & _
                      " h" & ChrW(7871) & "t h" & ChrW(7841) & "n (401)."
        Case "e403"
            VietMsg = "G" & ChrW(243) & "i hi" & ChrW(7879) & "n t" & ChrW(7841) & "i kh" & _
                      ChrW(244) & "ng " & ChrW(273) & ChrW(432) & ChrW(7907) & "c truy c" & _
                      ChrW(7853) & "p b" & ChrW(7897) & " d" & ChrW(7919) & " li" & ChrW(7879) & _
                      "u n" & ChrW(224) & "y (403)."
        Case "e429"
            VietMsg = ChrW(272) & ChrW(227) & " h" & ChrW(7871) & "t l" & ChrW(432) & ChrW(7907) & _
                      "t g" & ChrW(7885) & "i trong th" & ChrW(225) & "ng (429). N" & ChrW(226) & _
                      "ng g" & ChrW(243) & "i t" & ChrW(7841) & "i vietdataverse.online/pages/pricing.html"
        Case "eNet"
            VietMsg = "Kh" & ChrW(244) & "ng k" & ChrW(7871) & "t n" & ChrW(7889) & "i " & _
                      ChrW(273) & ChrW(432) & ChrW(7907) & "c t" & ChrW(7899) & "i m" & _
                      ChrW(225) & "y ch" & ChrW(7911) & ". Ki" & ChrW(7875) & "m tra m" & _
                      ChrW(7841) & "ng, ho" & ChrW(7863) & "c b" & ChrW(7841) & "n " & _
                      ChrW(273) & "ang d" & ChrW(249) & "ng Excel cho Mac."
        Case "eOther"
            VietMsg = "M" & ChrW(225) & "y ch" & ChrW(7911) & " tr" & ChrW(7843) & " l" & _
                      ChrW(7895) & "i"
        Case Else
            VietMsg = keyName
    End Select
End Function
