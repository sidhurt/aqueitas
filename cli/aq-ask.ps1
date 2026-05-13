param(
    [Parameter(ValueFromRemainingArguments=$true)]
    $ArgsList
)
python "$PSScriptRoot\aq-ask.py" @ArgsList
