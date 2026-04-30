$dir = "C:\CalibraWeb\procedures\templates\procedures"
Get-ChildItem $dir -Filter "*.html" | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $updated = $content -replace '{% block content %}', '{% block main_content %}'
    Set-Content $_.FullName $updated
    Write-Host "✓ $($_.Name) atualizado"
}
