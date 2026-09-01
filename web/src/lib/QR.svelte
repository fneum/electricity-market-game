<script>
  import qrcode from 'qrcode-generator';

  let { text, size = 200 } = $props();

  const svg = $derived.by(() => {
    const qr = qrcode(0, 'M'); // type 0 = auto-size, medium error correction
    qr.addData(text);
    qr.make();
    return qr.createSvgTag({ scalable: true, margin: 0 });
  });
</script>

<div class="qr" style="width:{size}px">
  <!-- svg is generated from our own game URL -->
  {@html svg}
</div>

<style>
  .qr {
    background: #fff;
    padding: 10px;
    border-radius: 12px;
    max-width: 100%;
  }
  .qr :global(svg) {
    display: block;
    width: 100%;
    height: auto;
  }
</style>
