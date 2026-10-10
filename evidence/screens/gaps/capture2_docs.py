"""Documentation shots (evidence-curator, 2026-10-04) for marks whose proof is the docs (deploy columns) or where the
running app cannot show the thing. Run under notes/comparison/demos/scale_probe/gap_run.sh with
  benchmark/scale/ceiling/.venv/bin/python <this file> [tool ...]
(tool words: vitessce ucsc scp cellxgene loupe; none = all)

vitessce   h01 hosted P: Data Hosting, 'Vitessce is a "serverless" tool' (no server, no accounts).
           h02 de N: the View Types list (every view the config can name; none computes a test).
ucsc       h01 remote P: 'Putting it onto the internet': the cbBuild output on S3 / GCS / Azure / github.io.
scp        h01 remote N: 'Uploading data overview': data enter through the upload wizard's Choose File.
cellxgene  h04 hosted P (row cellxgene-annotate): Annotate's '5_2 Self Host' page: web deployment not officially
           supported, no testing or support for several users on one instance (live page, archived copy as fallback).
loupe      h01 selection P: the interface tutorial's 'Lasso/rectangle selector: Select and label' (archived copy; the
           live 10x page sits behind a Vercel challenge). Captioned 'docs, not the app'.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capture2lib import TODAY, docs, log, pv  # noqa: E402
from capture2lib import step as _step  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

DRIVER = "evidence/screens/gaps/capture2_docs.py"
ARGS = sys.argv[1:]  # tool words to run (e.g. cellxgene loupe); none = all


def step(name, f):
    if ARGS and name.split()[0] not in ARGS:
        return None
    return _step(name, f)


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    p = b.new_page(viewport={"width": 1400, "height": 900})
    step("vitessce hosted", lambda: docs(
        p, tool="vitessce", name="h01_hosted_DOCS_serverless_data_hosting.jpg", url="https://vitessce.io/docs/data-hosting/",
        phrases=['is a "serverless" tool', "serverless", "can read data hosted in object stores"],
        proves=[pv("hosted", "P", f"docs, Vitessce (vitessce.io, read {TODAY}): Vitessce is 'serverless'; the app and the data are static files, so anyone can open it but there are no accounts or shared server state: P")],
        software=f"Vitessce docs, vitessce.io (read {TODAY}; app @vitessce 4.0.10)", driver=DRIVER))
    step("vitessce de", lambda: docs(
        p, tool="vitessce", name="h02_de_DOCS_view_types_list.jpg", url="https://vitessce.io/docs/components/",
        phrases=["Vitessce supports several view types", "several view types"],
        proves=[pv("de", "N", f"docs, Vitessce view types (vitessce.io, read {TODAY}): the full list of views a config can name; none computes a differential-expression test")],
        software=f"Vitessce docs, vitessce.io (read {TODAY}; app @vitessce 4.0.10)", driver=DRIVER,
        extra=[(3, ".table-of-contents", "every view type, listed (no DE view)")],
        note="Documentation, not the running app: the app has no view picker of its own; which views exist is fixed by this list and the config."))
    step("ucsc remote", lambda: docs(
        p, tool="ucsc-cell-browser", name="h01_remote_DOCS_internet_s3_gcs.jpg", url="https://cellbrowser.readthedocs.io/en/master/internet.html",
        phrases=["Amazon S3, Google Cloud Storage, Microsoft Azure", "Amazon S3", "copying the output of cbBuild"],
        proves=[pv("remote", "P", f"docs, UCSC Cell Browser (cellbrowser.readthedocs.io, read {TODAY}; cellbrowser 1.2.20): the cbBuild output can sit on S3, GCS, Azure or github.io and is read over HTTP, but only that pre-built format, not an h5ad or zarr in place: P")],
        software=f"UCSC Cell Browser docs, cellbrowser.readthedocs.io/en/master (read {TODAY}; cellbrowser 1.2.20)", driver=DRIVER,
        extra=[(3, "text=copying the output of >> nth=0", "only the cbBuild output is deployed")]))
    step("scp remote", lambda: docs(
        p, tool="single-cell-portal", name="h01_remote_DOCS_upload_wizard_choose_file.jpg",
        url="https://singlecell.zendesk.com/hc/en-us/articles/360060610052-Uploading-data-overview",
        phrases=["to choose the file to upload", "Choose File", "upload wizard"],
        proves=[pv("remote", "N", f"docs, Single Cell Portal (singlecell.zendesk.com, read {TODAY}): data enter a study only through the upload wizard (Choose File, or gcloud into SCP's own bucket); no field takes a user URL, S3 or GCS path")],
        software=f"Single Cell Portal docs, singlecell.zendesk.com (read {TODAY}; portal 1.20.0)", driver=DRIVER,
        extra=[(3, "text=Overview of the upload wizard >> nth=0", "the upload wizard")],
        note="Documentation, not the running app: the upload wizard needs a Google sign-in, which the audit does not use."))

    def cxg_hosted():
        live = "https://cellxgene.cziscience.com/docs/05__Annotate%20and%20Analyze%20Your%20Data/5_2__Self%20Host%20cellxgene"
        arch = "https://web.archive.org/web/20260516121220/" + live
        kw = dict(tool="cellxgene", name="h04_hosted_DOCS_annotate_self_host_no_multi_user.jpg",
                  phrases=["no testing or official support for deployments where multiple users", "multiple users are accessing the same Annotate instance",
                           "special consideration in any multi-user or hosted environment"],
                  proves=[dict(pv("hosted", "P", f"docs, CELLxGENE Annotate '5_2 Self Host' (cellxgene.cziscience.com, read {TODAY}; Annotate 1.3.0): web deployment is "
                                  "'not officially supported' and there is 'no testing or official support' for several users on one Annotate instance; "
                                  "the page cautions about multi-user or hosted use but documents no multi-user deployment: P"), row="cellxgene-annotate")],
                  software=f"CELLxGENE Annotate docs, cellxgene.cziscience.com (read {TODAY}; Annotate 1.3.0)", driver=DRIVER, wait=8,
                  extra=[(3, "text=officially support web deployment >> nth=0", "web deployment not officially supported")])
        if docs(p, url=live, **kw) is None:
            log("cellxgene hosted: live page failed, trying the archived copy")
            docs(p, url=arch, note="Archived copy (web.archive.org, 2026-05-16) of the live page, which did not render the phrase in this run.", **kw)
    step("cellxgene hosted", cxg_hosted)

    loupe_live = "https://www.10xgenomics.com/support/software/loupe-browser/latest/tutorials/introduction/lb-sc-interface-and-navigation"
    loupe_arch = "https://web.archive.org/web/20260613184701/" + loupe_live
    step("loupe selection", lambda: docs(
        p, tool="loupe", name="h01_selection_DOCS_lasso_select_and_label.jpg", url=loupe_arch,
        phrases=["Select and label an image area with an irregular shape", "Lasso/rectangle selector", "Mouse selector tools"],
        proves=[pv("selection", "P", f"docs, not the app: Loupe Browser 9.1.0 interface tutorial (10x, archived copy read {TODAY}): the Lasso/rectangle "
                   "selector 'Select[s] and label[s]' an area, so a selection becomes a labelled group that other panels then use, not a live linked highlight: P")],
        software=f"Loupe Browser 9.1.0 DOCS PAGE (10x website, archived copy read {TODAY}), not the app", driver=DRIVER,
        kind="docs, not the app", wait=8,
        banner_text=f"10x DOCS PAGE (archived copy), not the app (Loupe Browser was not run): {loupe_live}",
        extra=[(3, "text=Mouse selector tools >> nth=0", "Mouse selector tools")],
        note="Docs, not the app: Loupe Browser needs a 10x account, which the audit does not create. Archived copy "
             "(web.archive.org, 2026-06-13) because the live 10x page sits behind a Vercel bot challenge."))
    b.close()
log("done")
