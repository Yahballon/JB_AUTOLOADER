// SPDX-License-Identifier: GPL-3.0-or-later
// A debug-mode .pkg, not a mislabeled folder ZIP or UFS2 .ffpkg.
using System;
using System.IO;
using LibProsperoPkg;
using LibProsperoPkg.PKG;

if (args.Length != 2)
    throw new ArgumentException("Usage: Packager <prepared PPSA99767 app dir> <output dir>");
string app = Path.GetFullPath(args[0]);
string output = Path.GetFullPath(args[1]);
if (!File.Exists(Path.Combine(app, "eboot.bin")) ||
    !File.Exists(Path.Combine(app,"sce_sys","param.json")) ||
    !File.Exists(Path.Combine(app,"assets","web","app","index.html")))
    throw new InvalidOperationException("Missing eboot, param or packaged offline exploit resources");
Directory.CreateDirectory(output);
const string id = "UP9000-PPSA99767_00-JAILBREAKMEPKG01";
var result = ProsperoPackageBuilder.Build(new ProsperoBuildOptions {
    Mode = ProsperoPackageMode.Application,
    OutputFormat = ProsperoOutputFormat.DebugImage,
    SourceFolder = app,
    OutputFolder = output,
    ContentId = id,
    TitleId = "PPSA99767",
    Title = "JAILBREAK ME",
    Version = "01.00",
    LicenseFree = true,
    FakeSignSelfModules = true,
    GenerateParamJsonIfMissing = false,
}, Console.WriteLine);
foreach (string warning in result.Warnings)
    Console.WriteLine("PACKAGER WARNING: " + warning);
var pkg = ProsperoPkgReader.Read(result.OutputPath);
Console.WriteLine("Experimental package: " + result.OutputPath);
Console.WriteLine("PKG parsed successfully; install & browser launch require PS5 hardware test");
