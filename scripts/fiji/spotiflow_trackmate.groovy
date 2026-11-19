#@ File(label="入力動画ファイル（AVI・TIFF・STK）") inputFile
#@ File(label="XML出力先フォルダ", style="directory") outputDir
#@ String(label="Spotiflowモデル", choices={"general", "fluo_live", "hybiss", "synth_complex"}, value="general") spotiflowModel
#@ String(label="Spotiflow Conda環境名", value="spotiflow") condaEnvironment
#@ String(label="Tracker", choices={"Simple LAP", "LAP"}, value="Simple LAP") trackerType
#@ Double(label="Linking max distance（動画の空間単位。校正がなければ pixel）", value=5.0) linkingDistance
#@ Double(label="Gap-closing max distance（同じ単位）", value=10.0) gapDistance
#@ Integer(label="Max frame gap", value=5) maxFrameGap
#@ Integer(label="並列スレッド数", value=4) numThreads
#@ Boolean(label="軌跡付きAVIを保存", value=true) saveOverlayAvi
#@ Double(label="AVI再生FPS", value=14.0) aviFps

// Runs TrackMate with the Spotiflow detector on one 2D time-lapse movie and saves the XML
// (and optionally a track overlay AVI), matching what the TrackMate GUI produces.
// For TrackMate 8 + TrackMate-Spotiflow. Run from Fiji > File > New > Script (Groovy).
// A movie opened as a Z stack (Z>1, T=1) is relabelled as a time series.
// Version history: docs/fiji-macro.md. Bump MACRO_VERSION whenever the processing changes.

import ij.IJ
import fiji.plugin.trackmate.Logger
import fiji.plugin.trackmate.Model
import fiji.plugin.trackmate.SelectionModel
import fiji.plugin.trackmate.Settings
import fiji.plugin.trackmate.TrackMate
import fiji.plugin.trackmate.io.TmXmlWriter
import fiji.plugin.trackmate.gui.displaysettings.DisplaySettingsIO
import fiji.plugin.trackmate.visualization.hyperstack.HyperStackDisplayer
import fiji.plugin.trackmate.action.CaptureOverlayAction
import ij.plugin.filter.AVI_Writer
import fiji.plugin.trackmate.spotiflow.SpotiflowDetectorFactory
import java.text.SimpleDateFormat

def MACRO_NAME = "spotiflow_trackmate.groovy"
def MACRO_VERSION = "0.0.2"

if (inputFile == null) throw new IllegalArgumentException("入力動画ファイルを選んでください")
if (!inputFile.isFile()) throw new IllegalArgumentException("入力動画ファイルが見つかりません: ${inputFile}")
if (outputDir == null) throw new IllegalArgumentException("XML出力先フォルダを選んでください")
if (!outputDir.isDirectory() && !outputDir.mkdirs()) {
    throw new IllegalArgumentException("出力フォルダを作れません: ${outputDir}")
}
if (!condaEnvironment?.trim()) throw new IllegalArgumentException("Conda環境名を入力してください")
if (linkingDistance <= 0 || gapDistance <= 0 || maxFrameGap < 1 || numThreads < 1 || (saveOverlayAvi && aviFps <= 0)) {
    throw new IllegalArgumentException("距離・フレーム差・スレッド数を確認してください")
}

// Check the input before creating any folder. Only the chosen movie is processed.
def extensions = ['avi', 'tif', 'tiff', 'stk'] as Set
def ext = inputFile.name.contains('.') ? inputFile.name.substring(inputFile.name.lastIndexOf('.') + 1).toLowerCase(Locale.ROOT) : ''
if (!extensions.contains(ext)) {
    throw new IllegalArgumentException("AVI/TIFF/STKファイルを選択してください: ${inputFile.name}")
}

// Write each run to a new folder so that an existing XML is never overwritten.
def dateLabel = new SimpleDateFormat("yyyyMMdd_HHmmss").format(new Date())
def runDir = new File(outputDir, "trackmate_${dateLabel}")
if (!runDir.mkdirs()) throw new IllegalStateException("結果フォルダを作れません: ${runDir}")
File[] files = [inputFile] as File[]

def logLines = ["${MACRO_NAME} v${MACRO_VERSION}"]
int succeeded = 0
int failed = 0

files.eachWithIndex { file, index ->
    def imp = null
    try {
        IJ.log("[${index + 1}/${files.length}] ${file.name}")
        imp = IJ.openImage(file.absolutePath)
        if (imp == null) throw new IllegalStateException("画像を読み込めません")
        if (imp.getNChannels() != 1) {
            throw new IllegalStateException("1チャンネル動画のみ対応です (C=${imp.getNChannels()})")
        }

        // e.g. Z=100, T=1 becomes Z=1, T=100. The pixel order is unchanged.
        if (imp.getNFrames() == 1 && imp.getNSlices() > 1) {
            int nFrames = imp.getNSlices()
            imp.setDimensions(1, 1, nFrames)
            imp.setOpenAsHyperStack(true)
            IJ.log("  Z→T に変更: Z=1, T=${nFrames}")
        }
        if (imp.getNSlices() != 1 || imp.getNFrames() < 2) {
            throw new IllegalStateException("2D時系列画像ではありません (Z=${imp.getNSlices()}, T=${imp.getNFrames()})")
        }
        // TrackMate reads the distances in the movie's spatial unit (pixel when uncalibrated).
        def spaceUnit = imp.getCalibration().getUnit() ?: "pixel"
        IJ.log("  距離の単位: ${spaceUnit}（linking=${linkingDistance}, gap closing=${gapDistance}）")

        def settings = new Settings(imp)
        settings.detectorFactory = new SpotiflowDetectorFactory()
        settings.detectorSettings = settings.detectorFactory.getDefaultSettings()
        settings.detectorSettings['SPOTIFLOW_PRETRAINED_MODEL'] = spotiflowModel
        settings.detectorSettings['CONDA_ENV'] = condaEnvironment.trim()
        settings.detectorSettings['TARGET_CHANNEL'] = 1

        // Look for the tracker in the current package (jaqaman), then the old one (sparselap).
        def trackerClassName = (trackerType == 'Simple LAP') ?
                'SimpleSparseLAPTrackerFactory' : 'SparseLAPTrackerFactory'
        Class trackerClass = null
        for (def pkg : ['jaqaman', 'sparselap']) {
            try {
                trackerClass = Class.forName("fiji.plugin.trackmate.tracking.${pkg}.${trackerClassName}")
                break
            } catch (ClassNotFoundException ignored) { }
        }
        if (trackerClass == null) {
            throw new IllegalStateException("${trackerClassName} が見つかりません。TrackMateを更新してください")
        }
        settings.trackerFactory = trackerClass.getDeclaredConstructor().newInstance()
        settings.trackerSettings = settings.trackerFactory.getDefaultSettings()
        settings.trackerSettings['LINKING_MAX_DISTANCE'] = linkingDistance.doubleValue()
        settings.trackerSettings['GAP_CLOSING_MAX_DISTANCE'] = gapDistance.doubleValue()
        settings.trackerSettings['MAX_FRAME_GAP'] = maxFrameGap.intValue()
        settings.trackerSettings['ALLOW_GAP_CLOSING'] = true
        settings.trackerSettings['ALLOW_TRACK_SPLITTING'] = false
        settings.trackerSettings['ALLOW_TRACK_MERGING'] = false
        // Keep every spot Spotiflow reports: Spotiflow already applies its own probability
        // threshold. 0 is TrackMate's built-in default (Settings.initialSpotFilterValue).
        settings.initialSpotFilterValue = 0.0d
        settings.addAllAnalyzers()

        def model = new Model()
        model.setLogger(Logger.IJ_LOGGER)
        def trackmate = new TrackMate(model, settings)
        trackmate.setNumThreads(numThreads.intValue())
        if (!trackmate.checkInput()) throw new IllegalStateException("TrackMate入力エラー: ${trackmate.getErrorMessage()}")
        if (!trackmate.process()) throw new IllegalStateException("TrackMate実行エラー: ${trackmate.getErrorMessage()}")

        def stem = file.name.replaceFirst(/\.[^.]+$/, '')
        def target = new File(runDir, "${stem}.xml")
        // The XML and the AVI share Fiji's TrackMate display settings.
        def displaySettings = DisplaySettingsIO.readUserDefault()
        displaySettings.setSpotVisible(true)
        displaySettings.setTrackVisible(true)
        def writer = new TmXmlWriter(target)
        writer.appendLog("${MACRO_NAME} v${MACRO_VERSION}: model=${spotiflowModel}, conda=${condaEnvironment.trim()}, tracker=${trackerType}, linking=${linkingDistance}, gapDistance=${gapDistance}, distanceUnit=${spaceUnit}, maxFrameGap=${maxFrameGap}, initialSpotFilter=${settings.initialSpotFilterValue}, threads=${numThreads}. Z-to-T applied when needed.")
        writer.appendModel(model)
        writer.appendSettings(settings)
        writer.appendDisplaySettings(displaySettings)
        writer.writeToFile()

        // Same as "Capture overlay" at the end of the TrackMate wizard. It draws on Fiji's
        // screen, so it does not work headless. The style comes from the TrackMate user defaults.
        def aviMessage = ""
        if (saveOverlayAvi) {
            def captured = null
            try {
                def displayer = new HyperStackDisplayer(
                    model, new SelectionModel(model), imp, displaySettings)
                displayer.render()
                displayer.refresh()

                captured = CaptureOverlayAction.capture(
                    trackmate, 1, imp.getNFrames(), Logger.IJ_LOGGER)
                if (captured == null || captured.getStackSize() != imp.getNFrames()) {
                    throw new IllegalStateException("キャプチャされたフレーム数が一致しません")
                }

                // Playback speed of the AVI only; unrelated to the acquisition frame interval.
                captured.getCalibration().fps = aviFps.doubleValue()
                def aviFile = new File(runDir, "${stem}_tracks.avi")
                new AVI_Writer().writeImage(
                    captured, aviFile.absolutePath, AVI_Writer.JPEG_COMPRESSION, 90)
                if (!aviFile.isFile() || aviFile.length() == 0) {
                    throw new IllegalStateException("AVIの保存に失敗しました")
                }
                aviMessage = ", avi=${aviFile.name}"
                IJ.log("  AVI saved: ${aviFile.absolutePath}")
            } finally {
                if (captured != null) {
                    captured.changes = false
                    captured.close()
                }
            }
        }

        succeeded++
        def message = "OK ${file.name} -> ${target.name}${aviMessage} (spots=${model.getSpots().getNSpots(true)}, tracks=${model.getTrackModel().nTracks(true)})"
        IJ.log("  ${message}")
        logLines << message
    } catch (Exception ex) {
        failed++
        def message = "ERROR ${file.name}: ${ex.class.simpleName}: ${ex.message}"
        IJ.log("  ${message}")
        // Full stack trace for whoever investigates the failure.
        def trace = new StringWriter()
        ex.printStackTrace(new PrintWriter(trace))
        IJ.log(trace.toString())
        logLines << message
    } finally {
        if (imp != null) {
            imp.changes = false
            imp.close()
        }
    }
}
new File(runDir, 'batch_log.txt').setText(logLines.join(System.lineSeparator()), 'UTF-8')
IJ.log("完了 (${MACRO_NAME} v${MACRO_VERSION}): 成功=${succeeded}, 失敗=${failed}, 出力先=${runDir.absolutePath}")
IJ.showMessage("Spotiflow TrackMate v${MACRO_VERSION}", "成功: ${succeeded}本 / 失敗: ${failed}本\n結果: ${runDir.absolutePath}\n詳細: batch_log.txt")
