import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PitViewComponent } from './pit-view.component';

describe('PitViewComponent', () => {
  let component: PitViewComponent;
  let fixture: ComponentFixture<PitViewComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ PitViewComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(PitViewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
