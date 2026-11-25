$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Speech

$ffmpegRoot = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe'
$ffprobePath = (Get-ChildItem $ffmpegRoot -Recurse -Filter ffprobe.exe | Select-Object -First 1).FullName
$ffmpegPath = Join-Path (Split-Path $ffprobePath) 'ffmpeg.exe'
$baseVideo = Join-Path $env:TEMP 'jnana-all-roles-ready.mp4'
$outputVideo = Join-Path $PSScriptRoot 'jnana-sethu-all-roles-demo.mp4'
$managementAudio = Join-Path $env:TEMP 'jnana-management-narration.wav'
$facultyAudio = Join-Path $env:TEMP 'jnana-faculty-narration.wav'
$studentAudio = Join-Path $env:TEMP 'jnana-student-narration.wav'

$managementNarration = @'
Welcome to the management workspace. The institution overview summarizes active learners, average mastery, syllabus coverage, and students needing support. The activity chart tracks recent learning events. Course performance provides the next drill-down: open a course, inspect topic-level mastery, and identify where support is concentrated. Adoption combines weekly activity with syllabus readiness and assessment completion. Use the course filter on the intervention queue to focus on topics below the mastery threshold. Reports bring adoption, readiness, and follow-up signals together for review. These are sample cohort records. This project tracks course and topic levels, not departments or institutional cohorts.
'@

$facultyNarration = @'
Next is the faculty workspace. The class overview brings enrollment, class mastery, pending question drafts, and topics to reteach together. Syllabus mapping shows ready course material and the class-creation workflow. Question drafts remain private until a faculty member reviews and approves them. Assessments define the topic, schedule, duration, and whether AI support is allowed. The class gap map compares learner mastery by topic so weaker concepts stand out. AI controls display the assessment boundary, and reports summarize the class's recorded outcomes. The example uses a five-student cohort and one pending question set.
'@

$studentNarration = @'
The student dashboard combines overall mastery, practice activity, recommended learning steps, and the next scheduled assessment. My Courses opens the enrolled subject. The learning path organizes study into subjects, topics, and subtopics, with mastery statuses to guide attention. A structured lesson supports focused study. The study kit adds a summary, interactive flashcards, and a worked-example guide. Topic quizzes score practice and update mastery. The diagnostic checks understanding across the syllabus. Progress highlights strengths and focus areas, while Tests lists faculty schedules and AI-support rules. Learning Support opens tutor chat. This walkthrough uses sample data and a local mock language model, so generated responses are illustrative.
'@

function Write-NarrationWave {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
    try {
        $voice.SelectVoice('Microsoft Zira Desktop')
        $voice.Rate = 0
        $voice.Volume = 100
        $voice.SetOutputToWaveFile($Path)
        $voice.Speak($Text)
    }
    finally {
        $voice.Dispose()
    }
}

function Get-MediaDuration {
    param([Parameter(Mandatory = $true)][string]$Path)
    $value = & $ffprobePath -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $Path
    return [double]::Parse($value, [Globalization.CultureInfo]::InvariantCulture)
}

if (-not (Test-Path $baseVideo)) {
    throw "Base recording not found: $baseVideo"
}

Write-NarrationWave -Text $managementNarration -Path $managementAudio
Write-NarrationWave -Text $facultyNarration -Path $facultyAudio
Write-NarrationWave -Text $studentNarration -Path $studentAudio

$videoDuration = Get-MediaDuration -Path $baseVideo
$managementDuration = Get-MediaDuration -Path $managementAudio
$facultyDuration = Get-MediaDuration -Path $facultyAudio
$studentDuration = Get-MediaDuration -Path $studentAudio
$facultyStartMs = 60000
$studentStartMs = 100000

if ($managementDuration * 1000 -gt $facultyStartMs) {
    $facultyStartMs = [int][Math]::Ceiling(($managementDuration + 1) * 1000)
}
if (($studentStartMs / 1000) -lt ($facultyStartMs / 1000 + $facultyDuration + 1)) {
    $studentStartMs = [int][Math]::Ceiling(($facultyStartMs / 1000 + $facultyDuration + 1) * 1000)
}
if (($studentStartMs / 1000 + $studentDuration) -gt $videoDuration) {
    throw 'Narration runs past the end of the video. Shorten the script or slow the section timings.'
}

$filter = "[1:a]adelay=0:all=1[management];[2:a]adelay=${facultyStartMs}:all=1[faculty];[3:a]adelay=${studentStartMs}:all=1[student];[management][faculty][student]amix=inputs=3:duration=longest:dropout_transition=0,loudnorm=I=-16:TP=-1.5:LRA=11,apad[audio]"
$durationArg = $videoDuration.ToString('0.###', [Globalization.CultureInfo]::InvariantCulture)

& $ffmpegPath -hide_banner -loglevel error -y `
    -i $baseVideo `
    -i $managementAudio `
    -i $facultyAudio `
    -i $studentAudio `
    -filter_complex $filter `
    -map '0:v:0' -map '[audio]' `
    -c:v copy -c:a aac -b:a 128k -ar 48000 -ac 2 `
    -movflags +faststart -t $durationArg `
    $outputVideo

if ($LASTEXITCODE -ne 0) {
    throw 'FFmpeg failed to mux the narration into the demo video.'
}

Write-Output "Narrated demo saved to: $outputVideo"
Write-Output "Narration lengths (seconds): management=$managementDuration faculty=$facultyDuration student=$studentDuration"
Write-Output "Narration starts (seconds): management=0 faculty=$($facultyStartMs / 1000) student=$($studentStartMs / 1000)"