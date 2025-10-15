
import io
from typing import List, Tuple
from PIL import Image, ImageOps
import streamlit as st
import zipfile

st.set_page_config(page_title="Ukio Watermark", page_icon="🖼️", layout="centered")

st.title("Ukio • Watermark de imágenes")
st.caption("Sube tus fotos y aplica la marca de agua centrada, con transparencia y tamaño ajustables.")

with st.expander("⚙️ Opciones", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        opacity = st.slider("Transparencia del watermark", 0, 100, 50, help="0 = invisible, 100 = opaco")
        scale = st.slider("Tamaño relativo del watermark ( % del ancho de la foto )", 5, 60, 20)
    with col2:
        out_format = st.selectbox("Formato de salida", ["Mantener formato original", "JPEG", "PNG", "WEBP"])
        jpeg_quality = st.slider("Calidad JPG/WEBP", 60, 100, 90)

default_wm_path = "assets/ukio_watermark.png"
st.subheader("1) Marca de agua")
wm_file = st.file_uploader("Sube tu watermark (opcional)", type=["png", "jpg", "jpeg", "webp"])
if wm_file:
    wm = Image.open(wm_file).convert("RGBA")
else:
    try:
        wm = Image.open(default_wm_path).convert("RGBA")
        st.caption("Usando watermark por defecto: `assets/ukio_watermark.png`")
    except Exception:
        st.warning("No se encontró watermark por defecto. Sube uno arriba.")
        wm = None

st.subheader("2) Imágenes a procesar")
files = st.file_uploader("Selecciona una o varias imágenes", type=["png","jpg","jpeg","webp","tif","tiff"], accept_multiple_files=True)

def place_center(base: Image.Image, logo: Image.Image, opacity_pct: int, target_width_pct: int) -> Image.Image:
    """Devuelve una copia con el logo centrado. Escala el logo al % del ancho de la base."""
    base = base.convert("RGBA")
    logo = logo.convert("RGBA")
    # Escalado proporcional
    target_w = max(1, int(base.width * (target_width_pct / 100.0)))
    scale_ratio = target_w / logo.width
    target_h = max(1, int(logo.height * scale_ratio))
    logo_resized = logo.resize((target_w, target_h), Image.LANCZOS)

    # Opacidad
    if opacity_pct < 100:
        alpha = logo_resized.split()[-1]
        alpha = ImageOps.autocontrast(alpha)
        alpha = alpha.point(lambda p: p * (opacity_pct / 100.0))
        logo_resized.putalpha(alpha)

    # Pegar en el centro
    x = (base.width - target_w) // 2
    y = (base.height - target_h) // 2
    composed = base.copy()
    composed.alpha_composite(logo_resized, (x, y))
    return composed

st.divider()
process_btn = st.button("🔄 Procesar imágenes", use_container_width=True, type="primary")

results: List[Tuple[str, bytes, str]] = []
if process_btn:
    if not wm:
        st.error("Necesitas subir un watermark o disponer del watermark por defecto en assets.")
    elif not files:
        st.error("Sube al menos una imagen para procesar.")
    else:
        progress = st.progress(0.0, text="Procesando…")
        for idx, f in enumerate(files):
            try:
                img = Image.open(f)
                composed = place_center(img, wm, opacity, scale)

                # Determinar formato de salida
                orig_ext = (f.name.split(".")[-1] or "jpg").lower()
                if out_format == "Mantener formato original":
                    fmt = "JPEG" if orig_ext in ["jpg","jpeg"] else orig_ext.upper()
                    if fmt == "TIF": fmt = "TIFF"
                elif out_format == "JPEG":
                    fmt = "JPEG"
                elif out_format == "PNG":
                    fmt = "PNG"
                else:
                    fmt = "WEBP"

                buf = io.BytesIO()
                save_kwargs = {}
                if fmt in ["JPEG", "WEBP"]:
                    save_kwargs["quality"] = jpeg_quality
                if fmt == "JPEG":
                    # fondo blanco si hay transparencia
                    bg = Image.new("RGB", composed.size, (255, 255, 255))
                    bg.paste(composed, mask=composed.split()[-1])
                    bg.save(buf, fmt, **save_kwargs)
                else:
                    composed.save(buf, fmt, **save_kwargs)
                data = buf.getvalue()

                out_name = f.name.rsplit(".", 1)[0] + "_wm." + (fmt.lower() if fmt != "JPEG" else "jpg")
                results.append((out_name, data, fmt))
            except Exception as e:
                st.error(f"Error al procesar {f.name}: {e}")
            finally:
                progress.progress((idx + 1) / len(files), text=f"Procesando {idx + 1}/{len(files)}")

        progress.empty()

if results:
    st.success(f"✅ Procesadas {len(results)} imágenes.")
    for name, data, fmt in results:
        st.download_button(f"⬇️ Descargar {name}", data, file_name=name, mime=f"image/{'jpeg' if fmt=='JPEG' else fmt.lower()}")

    # ZIP
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data, _ in results:
            zf.writestr(name, data)
    st.download_button("📦 Descargar todas (ZIP)", zip_buf.getvalue(), file_name="ukio_watermarked.zip", mime="application/zip")
